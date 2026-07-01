# **Technical Design Document: Cofacts Infrastructure Migration to GCE (Ubuntu 24.04 LTS)**

---

## **1\. 執行摘要 (Executive Summary)**

本計畫旨在將 Cofacts 核心系統（包含 Elasticsearch、API、LINE Bots，以及現運行於 Cloud Run 的前端網站）整併並遷移至單一台 Google Compute Engine (GCE) 上。

基於第一階段概念驗證 (PoC) 的結果，作業系統將從原訂的 Container-Optimized OS (COS) 策略性轉向為 **Ubuntu 24.04 LTS**，網路架構確認採用**暫時性外部 IP (Ephemeral IP)** 搭配**入站全關 (Deny All Ingress)** 的策略。配合 Cloudflare Tunnel 實現 Zero Trust 網路，與 Google Cloud Ops Agent 深度監控，達成降低維運成本、免除 Cloud NAT 流量費，並為未來 ES9 \+ Gemini 多模態混合搜尋提供穩定、高可觀測性的硬體載體。

---

## **2\. 第一階段 (Phase 1\) 實驗結果與戰略轉向**

### **2.1 網路架構實務修正：避免 Cloud NAT 成本**

**發現 (Findings)**：在原先規劃的「無外部 IP (None)」模式下，VM 無法主動連向外網抓取 Docker 映像檔或 GitHub 資源。若要解決此問題，必須額外建置 Cloud NAT，但這會產生額外的月費與高昂的資料處理費（每 GB $0.045 USD）。對於高流量的 Cofacts API 來說極不經濟。

**修正方案 (Strategic Pivot)**：Production 應採用「暫時性外部 IP (Ephemeral External IP)」並配合「入站全關 (Deny All Ingress)」防火牆策略。

**優勢 (Benefits)**：

- **零成本**：完美避開 Cloud NAT 的資料處理費，極具經濟效益。  
- **高效能**：出站封包不需經過 NAT 轉發，網路延遲更低。  
- **安全性不減**：由於 GCP 防火牆已阻擋所有 0.0.0.0/0 的入站流量，其安全性等級實質上與「無外部 IP」相同。所有外部存取仍必須強制通過 Cloudflare Tunnel 進入。

### **2.2 COS 的實作限制與痛點**

- **安全分區限制 (noexec /home)**：COS 預設將 /home 掛載為 noexec，導致無法直接在使用者家目錄下執行 docker-compose 等二進制插件。強行掛載至 /var/lib/docker 等 exec 分區不僅破壞了標準化，也大幅增加了 Startup Script 的複雜度。  
- **唯讀系統檔案系統 (Read-only /usr)**：主要系統路徑皆為唯讀，導致持久化安裝 CLI 工具時需要非標準的路徑映射。  
- **OS Login 權限衝突**：在 OS Login 模式下，自動管理 docker 群組權限較為繁瑣，容易導致使用者登入後發生 Permission Denied 或無法正確載入 DOCKER\_CONFIG。

### **2.3 觀察指標與監控 (Observability Gap)**

- **Ops Agent 支援度不足**：COS 並非 Google Cloud Ops Agent 的首選作業系統，這導致無法實現對應用程式（如未來的 Elasticsearch 9）進行深層的指標監控與日誌整合。  
- **診斷工具缺乏**：COS 缺乏 apt 等套件管理工具。當發生 OOM 或網路延遲等瓶頸時，無法快速安裝診斷工具進行排查。

### **2.4 轉向建議：Ubuntu 24.04 LTS**

- **一鍵監控**：完整支援 Ops Agent，自動收集系統指標與應用程式日誌，對 ES9 效能調校至關重要。  
- **標準化 Docker 環境 (DX)**：原生支援最新的 Docker Engine 與 Compose V2，初始化指令極簡化，符合主流 DevOps 慣例。  
- **維運彈性**：具備完整套件管理工具，有利於 Phase 2 的效能調校與故障診斷。省下的開發工時遠大於系統輕量化帶來的效益。

---

## **3\. 目標架構 (Target Architecture)**

- **運算資源**：GCE e2-highmem-4 (4 vCPU, 32GB RAM)，Region: asia-east1。  
- **作業系統**：Ubuntu 24.04 LTS。  
- **容器化管理**：使用 Ubuntu 內建套件（`docker.io`, `docker-compose-v2`）。  
- **網路安全 (Zero Trust)**：  
  - GCE 配置暫時性外部 IP (Ephemeral IP) 供系統主動向外連線使用。  
  - 配合 GCP 防火牆落實入站全關 (Deny All Ingress) 原則，不開放任何 Inbound 防火牆 Port（包含 80/443）。  
  - 所有的外部流量（Web, API, Webhooks）一律由 GCE 內部的 cloudflared 容器主動向外建立連線。  
  - 開發者遠端連線僅透過 GCP Identity-Aware Proxy (IAP) 進行 SSH 登入。  
- **權限與存取**：採用 GCP OS Login 機制，搭配 Linux `pam_group.so` 在 SSH 登入時自動將管理員加入 `docker` 群組，使其擁有操作 Docker 與存取 `/srv` 的權限（詳見第 4 節）。  
- **VM Service Account**：使用專屬 SA（`cofacts-vm@PROJECT_ID.iam.gserviceaccount.com`），僅授予 `roles/logging.logWriter` 與 `roles/monitoring.metricWriter`，不使用權限過大的 Default Compute Engine SA。  
- **可觀測性**：整合 Google Cloud Ops Agent 收集系統 CPU/Memory/Disk 負載與應用程式日誌。  
- **資料儲存**：使用 GCE 的 Persistent Disk (Balanced SSD)，掛載於 Docker 預設的 `/var/lib/docker`。

---

## **4\. 權限設計：OS Login \+ pam\_group.so**

### **背景與問題**

GCP OS Login 開啟後，每個 Google 帳號登入時會動態建立對應的 Linux user（例如 `user_example_com`），並且**不會自動加入任何共用群組**。若直接用 `usermod -aG docker someone` 的方式管理，必須在每個人首次登入後手動執行，既繁瑣又容易漏掉。

GCP 原本支援透過 Cloud Identity 的 POSIX Groups 功能來解決此問題，但該功能已於 2024 年 9 月正式棄用，且無替代方案。

### **解決方案：pam\_group.so**

Linux PAM 的 `pam_group.so` 模組可在 SSH 登入時，根據 `/etc/security/group.conf` 的規則**自動指派補充群組（supplementary groups）**，無需事先知道使用者名稱，也無需 `usermod`。

GCP OS Login 的 guest environment 已在 PAM sshd stack 中配置了 `pam_group.so`，因此只需要正確設定 `group.conf` 即可生效。

### **設計原則**

| 角色 | GCP IAM Role | Linux 群組 | 可做什麼 |
| :---- | :---- | :---- | :---- |
| 管理員 | `roles/compute.osAdminLogin` | `docker` | 操作 Docker、存取 `/srv`、管理 cron |
| 唯讀登入 | `roles/compute.osLogin` | （無） | 僅能登入，不能操作 Docker |

加人：在 GCP IAM 指派 `roles/compute.osAdminLogin` → 下次 SSH 登入自動取得 `docker` 群組。 移人：在 GCP IAM 撤銷 Role → 立即無法登入（IAP 層攔截）。

---

## **5\. 分階段轉移策略 (Migration Phases)**

### **Phase 1：概念驗證與 Ubuntu 環境自動化 (PoC)**

**步驟一：開啟測試機器**

將 cloud-init 內容（見步驟二）存成 `/tmp/cloud-init.yaml`，再執行：

```shell
gcloud compute instances create <INSTANCE_NAME> \
  --project=<PROJECT_ID> \
  --zone=<ZONE> \
  --machine-type=e2-small \
  --image-family=ubuntu-2404-lts-amd64 \
  --image-project=ubuntu-os-cloud \
  --metadata=enable-oslogin=TRUE \
  --metadata-from-file=user-data=/tmp/cloud-init.yaml
```

**重點**：

- 必須加 `--metadata=enable-oslogin=TRUE`，否則 OS Login 不會啟用，pam\_group.so 的 docker 群組設定不會生效。  
- 不加 `--no-address`，讓 VM 有 Ephemeral IP 才能對外抓套件與 Docker image。GCP 防火牆預設隱式 Deny All Ingress，安全性不減。

**步驟二：Cloud-init 初始化設定**

所有初始化工作都放在 cloud-init（`user-data`）即可。`setfacl`、修改 `/etc/security/group.conf` 的結果全部寫在 Persistent Disk 上，reboot 後完全保留，不需要額外的 Startup Script。

```
#cloud-config
package_update: true

swap:
  filename: /swapfile
  size: 2G
  maxsize: 2G

packages:
  - git
  - htop
  - docker.io
  - docker-compose-v2
  - acl

runcmd:
  # 啟用 Docker service
  - systemctl enable --now docker

  # 設定 pam_group.so：SSH 登入時自動加入 docker 群組
  # 必須用 printf 而非 echo：GCE guest-agent 寫的最後一行沒有 trailing newline，
  # 直接 echo 會黏在同一行導致 pam 解析失敗、docker 群組無法套用。
  - printf '\nsshd;*;*;Al0000-2400;docker\n' >> /etc/security/group.conf

  # 自動 Clone Cofacts 部署專案到 /srv
  - git clone https://github.com/cofacts/rumors-deploy.git /srv/rumors-deploy

  # 設定 /srv 共用目錄權限
  # - chown root:docker：群組擁有者為 docker
  # - chmod 2775：setgid bit 讓新建檔案自動繼承 docker 群組
  # - setfacl default：確保新建檔案有群組寫入權，不受個人 umask 影響
  - chown root:docker /srv/rumors-deploy
  - chmod 2775 /srv/rumors-deploy
  - setfacl -d -m g::rwx /srv/rumors-deploy

  # 安裝 Google Cloud Ops Agent
  - curl -sSO https://dl.google.com/cloudagents/add-google-cloud-ops-agent-repo.sh
  - bash add-google-cloud-ops-agent-repo.sh --also-install
```

**步驟三：確認登入與操作**

機器啟動後，cloud-init 會在背景執行（安裝套件、Ops Agent 需要 3-5 分鐘）。具備 `roles/compute.osAdminLogin` 權限的管理員可先透過 IAP SSH 登入：

```shell
gcloud compute ssh <INSTANCE_NAME> --zone=<ZONE> --tunnel-through-iap --project=<PROJECT_ID>
```

等待 cloud-init 完成：

```shell
cloud-init status --wait
```

**完成後重新登入**（logout 再 ssh），才能套用 pam\_group.so 的群組設定。再執行 `id` 確認：

```shell
id
# uid=... groups=...,docker(XXX)
```

此時無需任何 `sudo`，可直接操作：

```shell
cd /srv/rumors-deploy
docker compose ps
docker compose up -d
```

**步驟四：設定環境變數**

```shell
cd /srv/rumors-deploy

# 複製預設環境變數（依照 rumors-deploy 慣例）
cp .env.sample .env
nano .env
# 填入資料庫連線等必要設定，並補上 Cloudflare Tunnel Token：
# TUNNEL_TOKEN=eyJhIjoi...
```

**步驟五：建立 docker-compose.yml**

因 rumors-deploy 已將 `docker-compose.yml` 列入 `.gitignore`（由各部署環境自行建立），直接在目錄下建立主設定檔，並結合 Cofacts 服務與 Cloudflare Tunnel：

```shell
cp docker-compose.sample.yml docker-compose.yml
# 然後對 docker-compose 進行編輯
```

**步驟六：啟動服務**

```shell
docker compose up -d
docker compose ps   # 確認所有 container 都順利運行
```

---

#### **重要：GCE 生命週期特性**

| 操作 | Cloud-init 重跑嗎 | Persistent Disk 資料 |
| :---- | :---- | :---- |
| 正常 Stop / Start | ❌ 不重跑 | ✅ 保留 |
| Reset | ❌ 不重跑 | ✅ 保留 |
| 刪除並重建 VM | ✅ 重新跑 | 視 Disk 是否保留 |

Reboot 後群組設定、目錄權限、PAM 設定全部保留（寫在 Persistent Disk 上）。只要 `docker-compose.yml` 中有設定 `restart: always`，機器重開機且 Docker daemon 啟動後，所有的 Cofacts 服務與 Tunnel 都會自動恢復運作。

---

### **Phase 2：正式環境建置 (Provisioning the Great Unification)**

1. **開啟正式機器**：Machine type: e2-highmem-4 (4 vCPU, 32GB RAM)。套用 Phase 1 的網路設定（Ephemeral IP \+ 入站全關）與 cloud-init 設定。  
2. **遷移 Secrets**：透過 `gcloud compute scp`，將 Linode 上的 `~/rumors-deploy/env-files/` 完整複製到 GCE 的專案目錄。  
3. **優化 docker-compose.yml**：  
   - 移除 nginx 服務與相關的 volume 掛載。  
   - 設定 cloudflared 定義 Ingress 規則，將 `api.cofacts.tw` 與 `cofacts.tw` 對應至內部 Port。  
   - 為 `url-resolver` 等可能出現 Memory Leak 的容器加上 `mem_limit: 512m`。

### **Phase 3：資料遷移與流量切換 (Data Migration & Cutover)**

1. **Elasticsearch 遷移策略**：Phase 3 以重現 ES6 環境為主，直接透過 Elasticsearch 的 Snapshot Backup & Restore 功能將 Linode 上的資料完整搬遷至 GCE。  
2. **後續升級與向量化**：在 ES6 成功搬遷並穩定運行後，再執行 ES6 升級至 ES9 的程序，並配合 Vertex AI Batch API 重建 Gemini Embedding 索引。  
3. **DNS / Cloudflare 切換 (Zero-Downtime)**：在 Cloudflare Tunnel 後台修改路由，將網域指向新 GCE 上建立的 Tunnel。  
4. **觀察與退租**：藉由 Google Cloud Ops Agent 儀表板觀察 1–2 週，無異常後關閉 Linode 與 Cloud Run。

---

## **6\. 維運操作 (Operations on Ubuntu)**

### **6.1 標準 Docker 操作**

管理員透過 IAP SSH 登入後，`pam_group.so` 自動完成群組套用，可直接在目錄下使用標準的 Compose V2 語法，**無需 sudo**：

```shell
cd /srv/rumors-deploy
docker compose ps
docker compose up -d
docker compose logs -f api
```

### **6.2 多人共同操作**

由於所有管理員都屬於 `docker` 群組，且 `/srv/rumors-deploy` 設有 setgid \+ default ACL，任何人建立或修改的檔案（包含 `.env`、`docker-compose.yml`）其他人都可以讀寫，不會出現 Permission Denied。

### **6.3 排程任務 (Cron Jobs)**

使用 `/etc/cron.d/` 管理共用 cronjob，所有管理員可見，不與個人帳號綁定：

```shell
# /etc/cron.d/cofacts-ops
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# 每日凌晨 1 點更新 image 並重啟（以 root 身份執行，因為 docker 群組在此已足夠）
0 1 * * *  root  cd /srv/rumors-deploy && docker compose pull && docker compose up -d
```

或採用 IaC 做法（推薦）：在 `docker-compose.yml` 中新增 `cron-runner` 容器，以符合基礎設施即代碼的精神。

### **6.4 除錯與系統監控**

- **即時查錯**：透過預先安裝的 `htop`，或隨時執行 `sudo apt install net-tools tcpdump` 進行網路封包追蹤。  
- **Ops Agent 儀表板**：所有機器的 CPU、Memory（包含 OS Page Cache，對 ES9 HNSW 向量搜尋至關重要）、Disk I/O 都可以直接在 GCP Console 的 Monitoring 視覺化圖表中查詢，徹底解決過去 Linode 時期缺乏長期系統負載指標的問題。

### **6.5 針對 AI 爬蟲的非對稱快取策略 (Asymmetric Caching for AI Crawlers)**

為因應大型語言模型 (LLM) 爬蟲對 Cofacts 資料庫的抓取需求，同時避免 ES9 搜尋引擎因高頻檢索而崩潰，實施以下非對稱快取策略：

* **自動化辨識 (Cloudflare Native AI Bot Detection)**: 直接利用 Cloudflare **Verified Bot Category** 功能，無需手動維護 User-Agent 清單。Cloudflare 會透過機器學習自動更新並標籤全球 AI 爬蟲（如 `GPTBot`, `ClaudeBot` 等）。  
    
* **實作配置 (Cache Rules)**:  
  1. **匹配條件**: `Verified Bot Category` 等於 `AI Crawler`。  
  2. **快取行為 (Cache Eligibility)**: 設定為「符合快取資格 (Eligible for cache)」。  
  3. **邊緣快取效期 (Edge TTL)**: 強制覆寫設定為 **7 天 (7 Days) 或更長**。  
  4. **忽略查詢參數**: 開啟「Ignore Query String」，防止爬蟲透過隨機參數穿透快取。


* **預期優點**:  
  * **算力保護**：99% 的 AI 爬蟲流量將在 Cloudflare 邊緣節點直接獲得回應，完全不會穿透回 GCE 伺服器，保護 CPU/RAM 資源。  
  * **使用者新鮮度不受限**：此規則僅針對 AI 分類流量生效。一般民眾、查核編輯與傳統搜尋引擎 (Googlebot) 仍依循標準規則，確保能即時看到最新的查核結果。  
  * **低維運成本**：完全基於基礎設施層級設定，免去修改應用程式碼與實作快取清除 API 的開發成本。

