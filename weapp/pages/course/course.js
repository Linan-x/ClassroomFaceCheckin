// 课程详情页 - 签到管理
const app = getApp();

Page({
  data: {
    courseName: '',
    hasActiveSession: false,
    currentSessionName: '',
    checkedCount: 0,
    totalCount: 0
  },

  onLoad(options) {
    const name = decodeURIComponent(options.name || '');
    this.setData({ courseName: name });
    app.globalData.currentCourse = name;
    this.loadSessionInfo();
  },

  onShow() {
    this.loadSessionInfo();
  },

  loadSessionInfo() {
    const name = this.data.courseName;
    // 加载签到次数和活跃session
    wx.request({
      url: app.globalData.serverUrl + '/api/course/' + encodeURIComponent(name) + '/sessions',
      success: (res) => {
        const sessions = res.data?.sessions || [];
        const activeId = res.data?.active;
        if (activeId && sessions.length) {
          const active = sessions.find(s => s.id === activeId);
          if (active) {
            this.setData({
              hasActiveSession: true,
              currentSessionName: active.name
            });
            // 加载签到结果
            wx.request({
              url: app.globalData.serverUrl + '/api/mobile/checkin/result?course=' + encodeURIComponent(name),
              success: (r2) => {
                if (r2.data) {
                  this.setData({
                    checkedCount: r2.data.checked_in || 0,
                    totalCount: r2.data.total || 0
                  });
                }
              }
            });
          }
        }
      }
    });
  },

  // 当前签到（继续）
  goCurrentCheckin() {
    const name = this.data.courseName;
    wx.request({
      url: app.globalData.serverUrl + '/api/course/' + encodeURIComponent(name) + '/sessions',
      success: (res) => {
        const activeId = res.data?.active;
        const sessions = res.data?.sessions || [];
        const active = sessions.find(s => s.id === activeId);
        if (active) {
          wx.navigateTo({
            url: '/pages/checkin/checkin?course=' + encodeURIComponent(name)
              + '&session=' + active.id + '&sessionName=' + encodeURIComponent(active.name)
          });
        } else {
          wx.showToast({ title: '没有活跃签到', icon: 'none' });
        }
      }
    });
  },

  // 新建签到
  goNewSession() {
    const name = this.data.courseName;
    const that = this;
    // 先获取现有次数
    wx.request({
      url: app.globalData.serverUrl + '/api/course/' + encodeURIComponent(name) + '/sessions',
      success(res) {
        const count = (res.data?.sessions || []).length + 1;
        wx.showModal({
          title: '新建签到',
          editable: true,
          content: '',
          placeholderText: '签到名称',
          success(modal) {
            const sname = modal.confirm && modal.content ? modal.content.trim() : '第' + count + '次签到';
            wx.showLoading({ title: '创建中...' });
            wx.request({
              url: app.globalData.serverUrl + '/api/course/' + encodeURIComponent(name) + '/sessions',
              method: 'POST',
              header: { 'Content-Type': 'application/json' },
              data: { name: sname },
              success(createRes) {
                wx.hideLoading();
                if (createRes.data?.success) {
                  const s = createRes.data.session;
                  wx.navigateTo({
                    url: '/pages/checkin/checkin?course=' + encodeURIComponent(name)
                      + '&session=' + s.id + '&sessionName=' + encodeURIComponent(s.name)
                  });
                } else {
                  wx.showToast({ title: '创建失败', icon: 'none' });
                }
              },
              fail() { wx.hideLoading(); wx.showToast({ title: '网络错误', icon: 'none' }); }
            });
          }
        });
      },
      fail() { wx.showToast({ title: '加载失败', icon: 'none' }); }
    });
  },

  // 签到历史
  goHistory() {
    wx.navigateTo({
      url: '/pages/history/history?course=' + encodeURIComponent(this.data.courseName)
    });
  },

  // 签到总览
  goOverview() {
    wx.navigateTo({
      url: '/pages/result/result?course=' + encodeURIComponent(this.data.courseName)
    });
  }
});
