太好了，畫面 OK，代表網域已經掛到 Cloudflare 了 🎉
接下來我們要做的是：把這個網域接到你家那台 uvicorn 後端上。
整體流程會是：

建立 Named Tunnel → 寫 config → 綁 DNS → 啟動 tunnel → 用 api.yuanshoushen.com 存取

我一步一步排好，你照順序來就行。

⸻

✅ Step 1：用 cloudflared 登入你的 Cloudflare 帳號

打開 Terminal，在你平常的 shell 裡跑：

cloudflared tunnel login

會發生： 1. 會開一個瀏覽器視窗，請你登入 Cloudflare 2. 它會問你要授權哪個帳號／網域
→ 選你的這個帳號，網域 yuanshoushen.com 3. 完成後，電腦上 ~/.cloudflared/ 會出現一個 cert.pem

這一步的目的：讓 cloudflared 之後可以幫你創建、管理 Named Tunnel。

⸻

✅ Step 2：建立一條「有名字的」 Tunnel

登入成功後，在 Terminal 繼續跑（名字你可以自己取，我先用 tcm-backend 當例子）：

cloudflared tunnel create tcm-backend

跑完會看到類似：

Created tunnel tcm-backend with id 12345678-abcd-....

也會在 ~/.cloudflared/ 多一個 json 檔，例如：

/Users/origin/.cloudflared/12345678-abcd-....json

請先記住這個 Tunnel ID（那串 UUID），等一下 config 要用。

⸻

✅ Step 3：建立 config.yml，指定要轉去哪一台（localhost:8000）

在 mac 上用 nano 開一個設定檔：

nano ~/.cloudflared/config.yml

貼進去這段（記得把路徑跟 tunnel id 換成你自己的）：

tunnel: tcm-backend
credentials-file: /Users/origin/.cloudflared/12345678-abcd-efgh-ijklmnop.json

ingress:

- hostname: api.yuanshoushen.com
  service: http://localhost:8000
- service: http_status:404

說明一下：
• tunnel: 填 Step 2 創的那個名稱
• credentials-file: 指向剛剛那個 json 檔完整路徑
• hostname: 代表之後要用的網址 → 我們讓 api.yuanshoushen.com 當後端入口
• service: 就是你本機的 uvicorn → http://localhost:8000
• 最後那行 http_status:404 是「預設丟 404」

存檔方式（nano）： 1. Ctrl + O → Enter（存檔） 2. Ctrl + X（離開）

⸻

✅ Step 4：讓這個 Tunnel 綁到 DNS（api.yuanshoushen.com）

在 Terminal 跑：

cloudflared tunnel route dns tcm-backend api.yuanshoushen.com

成功的話它會說類似：

Added CNAME api.yuanshoushen.com which will send traffic to this tunnel

你回去 Cloudflare Dashboard → 左邊點 DNS → Records，
會看到一筆新的 CNAME：

api.yuanshoushen.com CNAME <一長串>.cfargotunnel.com Proxied (橘色雲)

這樣 DNS 就接好了。

⸻

✅ Step 5：啟動你的 uvicorn 後端

照你原本方式啟動：

uvicorn server:app --host 0.0.0.0 --port 8000

只要本機 8000 有跑，就能被 Tunnel 轉到。

（之後你可以再把「一鍵啟動 uvicorn + cloudflared」寫成 script，目前先手動就好）

⸻

✅ Step 6：跑 Named Tunnel

再開一個 Terminal（或同一個也可以），跑：

cloudflared tunnel run tcm-backend

看到類似：

INF Connection established
INF Connected to api.yuanshoushen.com

就表示 Tunnel 正在幫你把外面的 api.yuanshoushen.com → 轉進 http://localhost:8000。

⸻

✅ Step 7：測試新網域

現在在任何地方（你的 Mac / 手機 4G）打：

curl https://api.yuanshoushen.com/live

或瀏覽器開：

https://api.yuanshoushen.com/live

如果有看到原本 /live 的畫面，就代表整條：

網域 → Cloudflare → Named Tunnel → 本地 uvicorn

已經串成功 ✅

⸻

建議你現在先做： 1. 在 Terminal 跑：cloudflared tunnel login 2. 跑：cloudflared tunnel create tcm-backend

跑完把 terminal 那段輸出（尤其是 tunnel id 那行）貼給我，我可以幫你把 config.yml 寫成「完全對你環境量身訂做」版。

位置：~/.cloudflared/
