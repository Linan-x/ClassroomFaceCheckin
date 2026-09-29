// 课程列表页（主页Tab）
const app = getApp();

Page({
  data: {
    courses: [],
    loading: true
  },

  onShow() {
    this.loadCourses();
  },

  loadCourses() {
    const that = this;
    this.setData({ loading: true });
    wx.request({
      url: app.globalData.serverUrl + '/api/mobile/courses',
      success(res) {
        let courses = [];
        if (res.statusCode === 200 && res.data && res.data.courses) {
          courses = res.data.courses;
        }
        that.setData({ courses, loading: false });
      },
      fail() {
        that.setData({ loading: false });
        wx.showToast({ title: '网络错误', icon: 'none' });
      }
    });
  },

  goCourse(e) {
    const name = e.currentTarget.dataset.name;
    app.globalData.currentCourse = name;
    wx.navigateTo({
      url: '/pages/course/course?name=' + encodeURIComponent(name)
    });
  }
});
