#!/usr/bin/env node

/**
 * preuninstall.js - npm 卸载前脚本
 * 清理配置（可选）
 */

const fs = require('fs');
const path = require('path');
const os = require('os');

const configDir = path.join(os.homedir(), '.erlangshen');

console.log('\n🧹 二郎神卸载中...');

// 检查是否要保留配置
if (process.env.ERLANG_SHEN_KEEP_CONFIG !== 'false') {
  console.log('\n⚠️  配置目录保留在:', configDir);
  console.log('   如需完全删除，请运行: rm -rf ~/.erlangshen');
}

console.log('\n👋 感谢使用二郎神，期待再见!\n');
