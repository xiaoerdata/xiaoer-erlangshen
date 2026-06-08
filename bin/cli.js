#!/usr/bin/env node

/**
 * erlangshen CLI - npm wrapper
 * 调用 Python 版二郎神
 */

const { spawn } = require('child_process');
const path = require('path');
const os = require('os');
const fs = require('fs');

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
  return path.resolve(__dirname, '..');
}

function getPythonInvocation(args) {
  const installDir = getInstallDir();

  if (args[0] === '--api') {
    const apiPath = path.join(installDir, 'src', 'api', 'server.py');
    if (!fs.existsSync(apiPath)) {
      console.error('当前 npm 用户端不包含服务端 API 代码，请在二郎神服务端仓库/生产环境启动 API。');
      process.exit(1);
    }
    return {
      args: ['-m', 'src.api.server', ...args.slice(1)]
    };
  }

  if (args[0] === '--enhanced') {
    const enhancedPath = path.join(installDir, 'src', 'api', 'cli_enhanced.py');
    if (!fs.existsSync(enhancedPath)) {
      console.error('当前 npm 用户端不包含旧版增强 CLI，请直接运行 erlangshen 或 erlangshen /help。');
      process.exit(1);
    }
    return {
      args: [enhancedPath, ...args.slice(1)]
    };
  }

  if (args[0] === '--cli' || args[0] === '--interactive') {
    return {
      args: ['-m', 'src.cli', ...args.slice(1)]
    };
  }

  return {
    args: ['-m', 'src.cli', ...args]
  };
}

// 获取命令行参数
const args = process.argv.slice(2);

// 合并环境变量，传递 DEEPSEEK_API_KEY
const env = { ...process.env };
const installDir = getInstallDir();
env.PYTHONPATH = env.PYTHONPATH
  ? `${installDir}${path.delimiter}${env.PYTHONPATH}`
  : installDir;

const python = getPythonPath();
const invocation = getPythonInvocation(args);

if (env.ERLANGSHEN_CLI_DEBUG === '1') {
  console.log(`启动二郎神: ${python} ${invocation.args.join(' ')}`);
}

const proc = spawn(python, invocation.args, {
  env,
  stdio: 'inherit',
  cwd: installDir
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
