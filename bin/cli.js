#!/usr/bin/env node

/**
 * erlangshen CLI - npm wrapper
 * 调用 Python 版二郎神
 */

const { spawn } = require('child_process');
const path = require('path');
const os = require('os');

// 获取 Python 路径
function getPythonPath() {
  const platform = os.platform();
  
  if (platform === 'win32') {
    return 'python';
  }
  
  // macOS/Linux 优先使用 python3
  return 'python3';
}

// 获取二郎神安装目录
function getInstallDir() {
  return path.dirname(require.main.filename);
}

// 获取二郎神 Python 脚本路径
function getScriptPath() {
  const installDir = getInstallDir();
  return path.join(installDir, 'src', 'api', 'cli_enhanced.py');
}

// 获取命令行参数
const args = process.argv.slice(2);

// 添加默认参数（CLI增强版）
if (!args.some(arg => arg.startsWith('--'))) {
  args.push('--enhanced');
}

// 合并环境变量，传递 DEEPSEEK_API_KEY
const env = { ...process.env };

// 执行二郎神
const python = getPythonPath();
const scriptPath = getScriptPath();

console.log(`🚀 启动二郎神...`);

const proc = spawn(python, [scriptPath, ...args], {
  env,
  stdio: 'inherit',
  cwd: process.cwd()
});

proc.on('exit', (code) => {
  process.exit(code || 0);
});

proc.on('error', (err) => {
  console.error('❌ 启动失败:', err.message);
  console.log('\n确保已安装 Python 3.9+ 和依赖：');
  console.log('  npm run postinstall');
  process.exit(1);
});
