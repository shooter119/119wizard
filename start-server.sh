#!/bin/bash
# 龙游县消防联系人查询系统 - 启动脚本

echo "=========================================="
echo "  龙游县消防联系人查询系统"
echo "=========================================="
echo ""
echo "正在启动本地服务器..."
echo ""

# 启动Flask服务器（LLM版）
python3 app_llm.py &

# 等待服务器启动
sleep 2

echo "✅ 服务器已启动！"
echo ""
echo "📱 访问地址："
echo "   http://localhost:5002/"
echo "   http://localhost:5002/cases"
echo "   http://localhost:5002/contacts"
echo ""
echo "💡 使用提示："
echo "   - 按住 Ctrl+C 可停止服务器"
echo "   - 修改文件后刷新页面即可看到变化"
echo ""
echo "=========================================="

# 自动打开浏览器
if [[ "$OSTYPE" == "darwin"* ]]; then
    open http://localhost:5002/
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    xdg-open http://localhost:5002/
fi

echo "浏览器已自动打开主页"
echo ""

# 保持运行
wait
