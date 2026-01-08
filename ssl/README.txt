SSL证书目录

本目录用于存放SSL/TLS证书文件，以支持HTTPS安全连接。

所需文件：
----------
1. fullchain.pem - SSL证书链文件（包含服务器证书和中间证书）
2. privkey.key   - SSL私钥文件

证书获取方式：
------------
1. Let's Encrypt（免费）：
   使用 certbot 工具可以免费获取和自动续期SSL证书
   命令示例：certbot certonly --standalone -d yourdomain.com

2. 商业证书颁发机构（CA）：
   从DigiCert、GlobalSign等机构购买商业SSL证书

3. 自签名证书（仅用于测试）：
   openssl req -x509 -newkey rsa:4096 -keyout privkey.key -out fullchain.pem -days 365 -nodes

配置说明：
----------
在 config.ini 文件的 [SSL] 节中配置以下选项：

[SSL]
ssl_enabled = true                    # 启用SSL（true/false）
ssl_cert_path = ssl/fullchain.pem    # 证书文件路径
ssl_key_path = ssl/privkey.key       # 私钥文件路径
https_only = false                    # 是否仅允许HTTPS访问

安全提示：
----------
⚠️ 私钥文件(privkey.key)包含敏感信息，请妥善保管
⚠️ 确保证书文件权限设置正确（建议：600或400）
⚠️ 定期检查证书有效期，及时续期
⚠️ 不要将私钥文件提交到版本控制系统
⚠️ 生产环境请使用受信任CA签发的证书，避免使用自签名证书

文件权限设置示例：
----------------
chmod 600 ssl/privkey.key
chmod 644 ssl/fullchain.pem
