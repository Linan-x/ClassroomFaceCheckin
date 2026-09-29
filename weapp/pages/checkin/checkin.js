// 实时签到页 - 快速拍照识别 + 实时提示
const app = getApp();

Page({
  data: {
    courseName: '',
    sessionName: '',
    totalCount: 0,
    checkedCount: 0,
    recentFaces: [],
    recognizing: false,
    faceCount: 0,
    lastSpeed: ''
  },

  sessionId: '',
  captureTimer: null,
  isCapturing: false,
  cameraCtx: null,
  checkedSet: new Set(),
  speedHistory: [],

  // 画布（人脸框）
  overlayCtx: null,
  canvasW: 0, canvasH: 0,
  canvasReady: false,
  lastFaces: [],
  drawTimer: null,

  onLoad(options) {
    const course = decodeURIComponent(options.course || '');
    const session = decodeURIComponent(options.session || '');
    const sessionName = decodeURIComponent(options.sessionName || '');
    this.setData({ courseName: course, sessionName });
    this.sessionId = session;
    app.globalData.currentCourse = course;

    this.initOverlay();
    this.loadCourseInfo();
  },

  onShow() {
    // 每次页面显示时重新加载签到状态（确保回退时数据最新）
    if (this.data.courseName) {
      this.loadCourseInfo();
    }
    this.cameraCtx = wx.createCameraContext();

    // 每 250ms 拍照上传（GPU 推理约 20ms/人）
    this.captureTimer = setInterval(() => {
      this.autoCapture();
    }, 250);
  },

  onUnload() {
    if (this.captureTimer) { clearInterval(this.captureTimer); this.captureTimer = null; }
    if (this.drawTimer) { clearInterval(this.drawTimer); this.drawTimer = null; }
  },

  initOverlay() {
    const that = this;
    const query = wx.createSelectorQuery();
    query.select('#faceCanvas').fields({ node: true, size: true }).exec(function(res) {
      if (!res || !res[0]) return;
      const canvas = res[0].node, ctx = canvas.getContext('2d');
      const dpr = wx.getSystemInfoSync().pixelRatio;
      canvas.width = res[0].width * dpr;
      canvas.height = res[0].height * dpr;
      ctx.scale(dpr, dpr);
      that.overlayCtx = ctx;
      that.canvasW = res[0].width;
      that.canvasH = res[0].height;
      that.canvasReady = true;
      that.drawTimer = setInterval(function() { that.drawFaces(); }, 50);
    });
  },

  drawFaces() {
    if (!this.canvasReady || !this.overlayCtx) return;
    const ctx = this.overlayCtx, w = this.canvasW, h = this.canvasH;
    ctx.clearRect(0, 0, w, h);
    const now = Date.now();
    (this.lastFaces || []).forEach(function(f) {
      if (!f.bbox) return;
      const x = f.bbox.x * w, y = f.bbox.y * h, bw = f.bbox.w * w, bh = f.bbox.h * h;
      const elapsed = now - (f.lastSeen || now);
      const alpha = Math.max(0.2, 1 - elapsed / 3000);
      if (alpha <= 0.2) return;
      ctx.globalAlpha = alpha;
      if (f.name) {
        ctx.strokeStyle = '#10b981'; ctx.lineWidth = 3;
        ctx.strokeRect(x, y, bw, bh);
        ctx.font = 'bold 14px sans-serif';
        const tw = ctx.measureText(f.name).width;
        ctx.fillStyle = 'rgba(16,185,129,0.85)';
        ctx.fillRect(x, y - 22, tw + 10, 22);
        ctx.fillStyle = '#fff';
        ctx.fillText(f.name, x + 5, y - 6);
      } else {
        ctx.strokeStyle = 'rgba(255,255,255,0.5)'; ctx.lineWidth = 2;
        ctx.strokeRect(x, y, bw, bh);
      }
    });
    ctx.globalAlpha = 1;
  },

  autoCapture() {
    if (this.isCapturing) return;
    this.isCapturing = true;
    this.setData({ recognizing: true });

    this.cameraCtx.takePhoto({
      quality: 'normal',
      success: (res) => {
        this.uploadPhoto(res.tempImagePath);
      },
      fail: () => {
        this.isCapturing = false;
        this.setData({ recognizing: false });
      }
    });
  },

  uploadPhoto(tempPath) {
    const that = this;
    const startTime = Date.now();

    wx.uploadFile({
      url: app.globalData.serverUrl + '/api/mobile/checkin',
      filePath: tempPath, name: 'image',
      formData: { course: that.data.courseName, session: that.sessionId },
      success(res) {
        const roundtrip = Date.now() - startTime;
        try {
          if (res.statusCode !== 200) {
            that.setData({ faceCount: 0, lastSpeed: 'HTTP ' + res.statusCode });
            return;
          }
          const data = JSON.parse(res.data);
          if (data.error) {
            that.setData({ faceCount: 0, lastSpeed: data.error });
            return;
          }
          if (data.success) {
            const now = Date.now();
            const newFaces = [];
            let newCheckins = 0;
            (data.faces || []).forEach(function(f) {
              newFaces.push({ name: f.name, confidence: f.confidence, bbox: f.bbox, lastSeen: now });
              if (f.name && !that.checkedSet.has(f.name)) {
                that.checkedSet.add(f.name);
                newCheckins++;
              }
            });
            // 更新显示列表：只显示已签到姓名
            that.lastFaces = newFaces;
            that.speedHistory.push(roundtrip);
            if (that.speedHistory.length > 5) that.speedHistory.shift();
            const avgSpeed = Math.round(that.speedHistory.reduce(function(a,b){return a+b;},0) / that.speedHistory.length);
            // 从 checkedSet 构建显示列表（兼容低版本 JS）
            var displayNames = [];
            that.checkedSet.forEach(function(n) { displayNames.push({ name: n }); });
            that.setData({
              faceCount: newFaces.length,
              lastSpeed: avgSpeed + 'ms',
              checkedCount: that.checkedSet.size,
              recentFaces: displayNames
            });
            if (newCheckins > 0) {
              wx.showToast({ title: '✅ 新签到 ' + newCheckins + ' 人', icon: 'success', duration: 1200 });
            }
          }
        } catch(e) {
          that.setData({ lastSpeed: '解析失败' });
        }
      },
      fail(err) {
        that.setData({ lastSpeed: '网络错误', faceCount: 0 });
      },
      complete() {
        that.isCapturing = false;
        that.setData({ recognizing: false });
      }
    });
  },

  loadCourseInfo() {
    const that = this;
    var url = app.globalData.serverUrl + '/api/mobile/checkin/result?course=' + encodeURIComponent(this.data.courseName);
    if (this.sessionId) { url += '&session=' + encodeURIComponent(this.sessionId); }
    wx.request({
      url: url,
      success: (res) => {
        if (res.statusCode === 200 && res.data) {
          // 只更新总数，checkedSet 仅从实时识别结果填充
          that.checkedSet.clear();
          var checkedList = res.data.checked_list || [];
          checkedList.forEach(function(n) { that.checkedSet.add(n); });
          that.setData({
            totalCount: res.data.total || 0,
            checkedCount: that.checkedSet.size,
            recentFaces: []
          });
        }
      }
    });
  },

  manualCapture() {
    const that = this;
    wx.showToast({ title: '拍照中...', icon: 'none' });
    this.cameraCtx.takePhoto({ quality: 'high',
      success(res) { that.uploadPhoto(res.tempFilePath); },
      fail() { wx.showToast({ title: '拍照失败', icon: 'error' }); }
    });
  },

  cameraError() {
    wx.showModal({ title: '摄像头错误', content: '请允许使用摄像头权限', showCancel: false });
  },

  endCheckin() {
    const that = this;
    wx.showModal({
      title: '结束签到',
      content: '确定结束本次签到吗？',
      success(res) {
        if (res.confirm) {
          // 通知服务端结束当前签到
          wx.request({
            url: app.globalData.serverUrl + '/api/course/' + encodeURIComponent(that.data.courseName) + '/sessions/end',
            method: 'POST',
            success() {
              if (that.captureTimer) { clearInterval(that.captureTimer); that.captureTimer = null; }
              if (that.frameListener) { that.frameListener.stop(); that.frameListener = null; }
              wx.showToast({ title: '签到已结束', icon: 'success' });
              setTimeout(function() { wx.navigateBack(); }, 1000);
            },
            fail() {
              wx.showToast({ title: '操作失败', icon: 'none' });
            }
          });
        }
      }
    });
  },

  goResult() {
    if (this.captureTimer) { clearInterval(this.captureTimer); this.captureTimer = null; }
    wx.navigateTo({ url: '/pages/result/result?course=' + encodeURIComponent(this.data.courseName) });
  }
});
