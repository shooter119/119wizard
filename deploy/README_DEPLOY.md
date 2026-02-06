# VPS 部署说明（119Wizard）

## 1. 准备
在本地项目根目录执行：

```bash
chmod +x /Users/vavavoom/Documents/test/deploy/deploy_vps.sh
```

## 2. 一键部署
```bash
/Users/vavavoom/Documents/test/deploy/deploy_vps.sh <user@host> <remote_app_dir> [ssh_key] [server_name]
```

示例：
```bash
/Users/vavavoom/Documents/test/deploy/deploy_vps.sh root@1.2.3.4 /opt/119wizard ~/.ssh/id_rsa 1.2.3.4
```

## 3. 常用运维命令（VPS 上）
```bash
sudo systemctl status 119wizard
sudo systemctl restart 119wizard
sudo journalctl -u 119wizard -n 200 --no-pager
sudo nginx -t
sudo systemctl restart nginx
```

## 4. 说明
- 应用运行在 Gunicorn + Systemd
- Nginx 反向代理到 `127.0.0.1:5002`
- 默认监听 `80` 端口
