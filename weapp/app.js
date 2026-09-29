// 课堂签到小程序 - 全局配置
App({
  globalData: {
    // 服务器地址 - 在微信开发者工具中调试时使用 http://127.0.0.1:5008
    // 真机调试时需要改为局域网 IP（如 http://192.168.x.x:5008）
    // 发布时需要改为正式域名（需配置合法域名白名单）
    serverUrl: 'http://linan.xyz:18088',
    currentCourse: null,
    checkinTotal: 0,
    checkedCount: 0
  }
});
