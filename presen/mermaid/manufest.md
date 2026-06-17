今後マーメイド図を更新したいときは：

# _mermaid/dif.md を編集した後
mmdc -i <.mmdファイル> -o presen/mermaid/<名前>.png -b white -w 1400 \
     --puppeteerConfigFile /tmp/puppeteer_config.json

/tmp/puppeteer_config.json は再起動すると消えるので、必要なら config/ に置いておくと楽です（ただし git 管理外）。
