#!/usr/bin/env node

/**
 * postinstall.js - npm 安装后脚本
 * 自动安装 Python 依赖
 */

const { spawn, execSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');

const installDir = path.dirname(require.main.filename);
const projectRoot = installDir;

console.log('📦 二郎神安装中...');
console.log(`   安装目录: ${installDir}`);

// 检查 Python 版本
function checkPython() {
  console.log('\n🔍 检查 Python 环境...');
  
  try {
    const python = os.platform() === 'win32' ? 'python' : 'python3';
    const version = execSync(`${python} --version`, { encoding: 'utf-8' }).trim();
    console.log(`   ✓ ${version}`);
    
    // 检查版本号
    const match = version.match(/Python (\d+)\.(\d+)/);
    if (match) {
      const major = parseInt(match[1]);
      const minor = parseInt(match[2]);
      
      if (major < 3 || (major === 3 && minor < 9)) {
        console.error('   ✗ Python 3.9+  required');
        process.exit(1);
      }
    }
    
    return python;
  } catch (e) {
    console.error('   ✗ Python 未安装');
    console.error('\n请先安装 Python 3.9+:');
    console.error('   macOS: brew install python3');
    console.error('   Linux: sudo apt install python3 python3-pip');
    console.error('   Windows: https://www.python.org/downloads/');
    process.exit(1);
  }
}

// 安装 Python 依赖
function installDependencies(python) {
  console.log('\n📚 安装 Python 依赖...');
  
  const requirementsPath = path.join(projectRoot, 'requirements.txt');
  
  if (!fs.existsSync(requirementsPath)) {
    console.log('   ⚠ requirements.txt not found, skipping');
    return;
  }
  
  return new Promise((resolve, reject) => {
    const pip = os.platform() === 'win32' ? 'pip' : 'pip3';
    
    // 使用 pip install -r requirements.txt
    const proc = spawn(python, ['-m', pip, 'install', '-r', requirementsPath, '--quiet'], {
      stdio: 'inherit',
      cwd: projectRoot
    });
    
    proc.on('close', (code) => {
      if (code === 0) {
        console.log('   ✓ 依赖安装完成');
        resolve();
      } else {
        console.error('   ✗ 依赖安装失败');
        reject(new Error(`pip exited with code ${code}`));
      }
    });
    
    proc.on('error', reject);
  });
}

// 创建配置目录
function createConfigDir() {
  console.log('\n⚙️  初始化配置目录...');
  
  const configDir = os.homedir();
  const erlangshenDir = path.join(configDir, '.erlangshen');
  
  if (!fs.existsSync(erlangshenDir)) {
    fs.mkdirSync(erlangshenDir, { recursive: true });
    console.log(`   ✓ 创建配置目录: ${erlangshenDir}`);
  } else {
    console.log(`   ✓ 配置目录已存在: ${erlangshenDir}`);
  }
  
  // 创建示例配置
  const configPath = path.join(erlangshenDir, 'config.toml');
  if (!fs.existsSync(configPath)) {
    const configTemplate = `# 二郎神配置文件
# https://github.com/xiaoerdata/xiaoer-erlangshen

# DeepSeek API Key (必需)
deepseek_api_key = ""

# 数据库配置 (可选，用于连接远程行情数据库)
[database]
host = ""
port = 3306
user = ""
password = ""

# 飞书配置 (可选，用于消息推送)
[feishu]
app_id = ""
app_secret = ""

# 代理配置 (可选)
[proxy]
enabled = false
http = ""
https = ""
`;
    
    fs.writeFileSync(configPath, configTemplate);
    console.log(`   ✓ 创建配置文件: ${configPath}`);
  }
}

// 验证安装
function verifyInstall(python) {
  console.log('\n✅ 验证安装...');
  
  try {
    // 测试导入二郎神
    const testCode = `
import sys
sys.path.insert(0, '${projectRoot.replace(/\\/g, '\\\\')}')
from src.core.brain import Brain
from src.core.investment_universe import get_universe
print('ok')
`;
    
    const result = execSync(python, ['-c', testCode], { encoding: 'utf-8' }).trim();
    
    if (result === 'ok') {
      console.log('   ✓ 二郎神验证通过');
      return true;
    }
  } catch (e) {
    console.log('   ⚠ 验证时出现警告 (可能缺少 API Key)');
  }
  
  return false;
}

// 主函数
async function main() {
  console.log('\n========================================');
  console.log('   二郎神 v0.1.0 - AI投资智能体');
  console.log('   https://github.com/xiaoerdata/xiaoer-erlangshen');
  console.log('========================================\n');
  
  try {
    const python = checkPython();
    await installDependencies(python);
    createConfigDir();
    verifyInstall(python);
    
    console.log('\n========================================');
    console.log('   ✓ 安装完成!');
    console.log('========================================');
    console.log('\n📖 使用方法:');
    console.log('   erlangshen --cli          # 启动CLI');
    console.log('   erlangshen --api           # 启动API服务');
    console.log('\n⚠️  首次使用请配置 API Key:');
    console.log('   vim ~/.erlangshen/config.toml');
    console.log('');
    
  } catch (e) {
    console.error('\n❌ 安装失败:', e.message);
    process.exit(1);
  }
}

main();
