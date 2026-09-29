// 签到历史页 - 显示每次签到的详细名单
const app = getApp();

Page({
  data: {
    courseName: '',
    sessions: [],
    loading: true
  },

  onLoad(options) {
    const course = decodeURIComponent(options.course || '');
    this.setData({ courseName: course });
    this.loadHistory(course);
  },

  loadHistory(course) {
    const that = this;
    wx.request({
      url: app.globalData.serverUrl + '/api/course/' + encodeURIComponent(course) + '/sessions',
      success(res) {
        const sessions = res.data?.sessions || [];
        if (!sessions.length) {
          that.setData({ loading: false });
          return;
        }
        // 加载每个session的签到结果
        let loaded = 0;
        sessions.forEach(function(s, idx) {
          wx.request({
            url: app.globalData.serverUrl + '/api/mobile/checkin/result?course=' + encodeURIComponent(course) + '&session=' + s.id,
            success(rr) {
              const d = rr.data || {};
              const checkedList = d.checked_list || [];
              const uncheckedList = d.unchecked || [];
              const total = d.total || 0;
              const checked = d.checked_in || 0;
              const rate = total > 0 ? Math.round(checked / total * 100) : 0;
              sessions[idx] = {
                ...s,
                total,
                checked,
                rate,
                checked_list: checkedList,
                unchecked_list: uncheckedList,
                _rate: rate,
                _open: false
              };
            },
            complete() {
              loaded++;
              if (loaded >= sessions.length) {
                that.setData({ sessions, loading: false });
              }
            }
          });
        });
      },
      fail() {
        that.setData({ loading: false });
        wx.showToast({ title: '加载失败', icon: 'none' });
      }
    });
  },

  toggleSession(e) {
    const idx = e.currentTarget.dataset.idx;
    const key = 'sessions[' + idx + ']._open';
    this.setData({ [key]: !this.data.sessions[idx]._open });
  },

  goBack() {
    wx.navigateBack();
  }
});
