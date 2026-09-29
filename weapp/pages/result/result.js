// 签到结果页
const app = getApp();

Page({
  data: {
    courseName: '',
    sessionName: '',
    sessionId: '',
    data: {
      total: 0,
      checked_in: 0,
      unchecked: [],
      checked_list: [],
      rate: '0%'
    }
  },

  onLoad(options) {
    const course = decodeURIComponent(options.course || '');
    const session = decodeURIComponent(options.session || '');
    const sessionName = decodeURIComponent(options.sessionName || '');
    this.setData({
      courseName: course,
      sessionName: sessionName,
      sessionId: session
    });
    this.loadResult(course, session);
  },

  loadResult(course, session) {
    const that = this;
    let url = app.globalData.serverUrl + '/api/mobile/checkin/result?course=' +
              encodeURIComponent(course);
    if (session) {
      url += '&session=' + encodeURIComponent(session);
    }

    wx.request({
      url: url,
      success(res) {
        if (res.statusCode === 200 && res.data) {
          that.setData({ data: res.data });
        }
      },
      fail() {
        wx.showToast({ title: '加载失败', icon: 'none' });
      }
    });
  },

  copyDashboard() {
    const url = app.globalData.serverUrl + '/dashboard/' +
                encodeURIComponent(this.data.courseName);
    wx.setClipboardData({
      data: url,
      success() {
        wx.showToast({ title: '大屏链接已复制' });
      }
    });
  },

  goBack() {
    wx.switchTab({
      url: '/pages/index/index'
    });
  }
});
