#!/usr/bin/env node

/**
 * postinstall.js - npm 安装后脚本
 * 自动安装 Python 依赖
 */

const { spawn, execSync, spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');

const installDir = path.resolve(__dirname, '..');
const projectRoot = installDir;
const defaultApiBaseUrl = 'https://xiaoerdata.site/api/erlangshen';

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
  
  const clientRequirementsPath = path.join(projectRoot, 'requirements-client.txt');
  const requirementsPath = fs.existsSync(clientRequirementsPath)
    ? clientRequirementsPath
    : path.join(projectRoot, 'requirements.txt');
  
  if (!fs.existsSync(requirementsPath)) {
    console.log('   ⚠ requirements file not found, skipping');
    return;
  }
  
  return new Promise((resolve, reject) => {
    // 使用 pip install -r requirements.txt
    const proc = spawn(python, ['-m', 'pip', 'install', '-r', requirementsPath, '--quiet'], {
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
  const configPath = path.join(erlangshenDir, 'settings.json');
  if (!fs.existsSync(configPath)) {
    const configTemplate = {
      llm_provider: 'deepseek',
      deepseek_api_key: '',
      deepseek_model: 'deepseek-chat',
      erlangshen_api_base_url: defaultApiBaseUrl,
      erlangshen_auth_login_entry: 'xwab',
      db_host: '',
      db_port: 5432,
      db_name: 'market',
      db_user: '',
      db_password: '',
      feishu_app_id: '',
      feishu_app_secret: '',
      proxy_enabled: false,
      http_proxy: '',
      https_proxy: ''
    };
    
    fs.writeFileSync(configPath, JSON.stringify(configTemplate, null, 2));
    console.log(`   ✓ 创建配置文件: ${configPath}`);
  } else {
    try {
      const config = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
      if (!config.erlangshen_api_base_url || config.erlangshen_api_base_url === 'http://127.0.0.1:8000') {
        config.erlangshen_api_base_url = defaultApiBaseUrl;
        fs.writeFileSync(configPath, JSON.stringify(config, null, 2));
        console.log(`   ✓ 更新默认服务端: ${defaultApiBaseUrl}`);
      }
    } catch (e) {
      console.log('   ⚠ 配置文件不是有效 JSON，保留现状');
    }
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
from src.cli import CLI
from src.client.server_client import ErlangshenServerClient
print('ok')
`;
    
    const result = spawnSync(python, ['-c', testCode], {
      cwd: projectRoot,
      encoding: 'utf-8'
    }).stdout.trim();
    
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
  console.log('   二郎神 v0.1.2 - AI投资智能体');
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
    console.log('   erlangshen');
    console.log(`   erlangshen /health          # 默认服务端: ${defaultApiBaseUrl}`);
    console.log('   erlangshen /auth server <服务端URL>');
    console.log('   erlangshen /login xwab <账号>');
    console.log('   erlangshen /status');
    console.log('   erlangshen /map <问题>');
    console.log('   erlangshen /advice <问题>');
    console.log('\n如需切换环境，可通过 ERLANGSHEN_API_BASE_URL 或 /auth server <url> 覆盖。');
    console.log('');
    
  } catch (e) {
    console.error('\n❌ 安装失败:', e.message);
    process.exit(1);
  }
}

main();
