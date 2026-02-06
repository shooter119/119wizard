# 119Wizard 更新部署手册

本文档用于你后续每次项目更新后的部署操作。

- 项目本地路径：`/Users/vavavoom/Documents/test`
- VPS：`root@154.12.33.253`
- VPS 部署目录：`/root/119wizard`
- 访问地址：`http://154.12.33.253`

## 一、标准流程（推荐，每次更新都用）

### 1. 本地进入项目
```bash
cd /Users/vavavoom/Documents/test
```

### 2. 本地测试（可跳过，但建议执行）
```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

### 3. 一键部署到 VPS
```bash
/Users/vavavoom/Documents/test/deploy/deploy_vps.sh root@154.12.33.253 /root/119wizard "" 154.12.33.253
```

### 4. 验证服务
```bash
ssh root@154.12.33.253
systemctl status 119wizard --no-pager
systemctl status nginx --no-pager
curl -I http://127.0.0.1:5002
curl -I http://154.12.33.253
```

预期：`HTTP/1.1 200 OK`

## 二、仅代码小改（VPS 已经部署好）

如果只是更新代码，不改系统服务配置，也可以手动同步后重启：

### 1. 同步代码（本地执行）
```bash
cd /Users/vavavoom/Documents/test
tar -C /Users/vavavoom/Documents/test -czf - \
  --exclude='.git' \
  --exclude='__pycache__' \
  --exclude='.DS_Store' \
  --exclude='venv' \
  --exclude='*.pyc' \
  . | ssh root@154.12.33.253 "tar -xzf - -C /root/119wizard"
```

### 2. VPS 重启服务
```bash
ssh root@154.12.33.253
cd /root/119wizard
./venv/bin/pip install -r requirements.txt
systemctl restart 119wizard
systemctl status 119wizard --no-pager
```

## 三、只重启服务（代码已在 VPS）

```bash
ssh root@154.12.33.253 "systemctl restart 119wizard && systemctl status 119wizard --no-pager"
```

## 四、查看日志（排障）

```bash
ssh root@154.12.33.253
journalctl -u 119wizard -n 200 --no-pager
journalctl -u nginx -n 200 --no-pager
```

## 五、Nginx 异常时修复

如果出现 Nginx 配置错误，执行：

```bash
ssh root@154.12.33.253
sed 's#__SERVER_NAME__#154.12.33.253#g' /root/119wizard/deploy/nginx.119wizard.conf > /tmp/119wizard.nginx.conf

if [ -d /etc/nginx/sites-available ] && [ -d /etc/nginx/sites-enabled ]; then
  cp /tmp/119wizard.nginx.conf /etc/nginx/sites-available/119wizard.conf
  ln -sf /etc/nginx/sites-available/119wizard.conf /etc/nginx/sites-enabled/119wizard.conf
  [ -f /etc/nginx/conf.d/119wizard.conf ] && rm -f /etc/nginx/conf.d/119wizard.conf
else
  mkdir -p /etc/nginx/conf.d
  cp /tmp/119wizard.nginx.conf /etc/nginx/conf.d/119wizard.conf
  [ -L /etc/nginx/sites-enabled/119wizard.conf ] && rm -f /etc/nginx/sites-enabled/119wizard.conf
fi

nginx -t && systemctl restart nginx
```

## 六、回滚（紧急）

如果发布后服务异常，先回滚到上一次可用代码（前提：你在 VPS 里有备份目录）：

```bash
# 例：假设你有 /root/119wizard_backup
ssh root@154.12.33.253
rm -rf /root/119wizard
cp -r /root/119wizard_backup /root/119wizard
systemctl restart 119wizard
```

建议你以后每次发布前在 VPS 先备份一次：
```bash
ssh root@154.12.33.253 "rm -rf /root/119wizard_backup && cp -r /root/119wizard /root/119wizard_backup"
```

---

如果你希望，我可以下一步把“发布前自动备份 + 发布后自动健康检查”也集成进 `deploy/deploy_vps.sh`，做到一次命令全自动。
