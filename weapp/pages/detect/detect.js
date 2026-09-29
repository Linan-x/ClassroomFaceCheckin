// 人脸检测测试页 - 使用 takePhoto 上传检测
const app = getApp();

Page({
  data: {
    faceCount: 0,
    maxFaces: 0,
    totalDetects: 0,
    detecting: false,
    lastDetectTime: '',
    detectInterval: '200ms'
  },

  cameraCtx: null,
  captureTimer: null,
  isCapturing: false,

  // 画布
  overlayCtx: null,
  canvasW: 0,
  canvasH: 0,
  canvasReady: false,
  drawTimer: null,
  lastFaces: [],

  onLoad() {
    this.initCanvas();
    this.cameraCtx = wx.createCameraContext();

    // 每 200ms 拍一张检测（MTCNN + GPU 约 5ms，瓶颈在 takePhoto 快门）
    this.captureTimer = setInterval(() => {
      this.captureAndDetect();
    }, 200);
  },

  onUnload() {
    if (this.captureTimer) { clearInterval(this.captureTimer); this.captureTimer = null; }
    if (this.drawTimer) { clearInterval(this.drawTimer); this.drawTimer = null; }
  },

  initCanvas() {
    const that = this;
    const query = wx.createSelectorQuery();
    query.select('#faceCanvas')
      .fields({ node: true, size: true })
      .exec(function(res) {
        if (!res || !res[0]) return;
        const canvas = res[0].node;
        const ctx = canvas.getContext('2d');
        const dpr = wx.getSystemInfoSync().pixelRatio;
        canvas.width = res[0].width * dpr;
        canvas.height = res[0].height * dpr;
        ctx.scale(dpr, dpr);
        that.overlayCtx = ctx;
        that.canvasW = res[0].width;
        that.canvasH = res[0].height;
        that.canvasReady = true;

        // 每 50ms 重绘人脸框
        that.drawTimer = setInterval(function() { that.drawBoxes(); }, 50);
      });
  },

  drawBoxes() {
    if (!this.canvasReady || !this.overlayCtx) return;
    const ctx = this.overlayCtx;
    const w = this.canvasW;
    const h = this.canvasH;
    ctx.clearRect(0, 0, w, h);

    (this.lastFaces || []).forEach(function(f) {
      if (!f) return;
      const x = f.x * w;
      const y = f.y * h;
      const bw = f.w * w;
      const bh = f.h * h;
      ctx.strokeStyle = '#10b981';
      ctx.lineWidth = 3;
      ctx.strokeRect(x, y, bw, bh);
    });
  },

  captureAndDetect() {
    if (this.isCapturing) return;
    this.isCapturing = true;
    this.setData({ detecting: true });

    this.cameraCtx.takePhoto({
      quality: 'low',
      success: (res) => {
        this.uploadForDetect(res.tempImagePath);
      },
      fail: () => {
        this.isCapturing = false;
        this.setData({ detecting: false });
      }
    });
  },

  uploadForDetect(tempPath) {
    const that = this;

    // 先用 uploadFile 上传图片
    wx.uploadFile({
      url: app.globalData.serverUrl + '/api/mobile/detect',
      filePath: tempPath,
      name: 'image',
      success(res) {
        try {
          const data = JSON.parse(res.data);
          if (data.success) {
            const faces = data.faces || [];
            const count = data.count || 0;
            const total = that.data.totalDetects + 1;
            const max = Math.max(that.data.maxFaces, count);
            that.setData({
              faceCount: count,
              totalDetects: total,
              maxFaces: max,
              lastDetectTime: new Date().toLocaleTimeString()
            });
            that.lastFaces = faces;
          } else if (data.error) {
            console.log('detect error:', data.error);
            wx.showToast({ title: data.error, icon: 'none' });
          }
        } catch(e) {
          console.log('parse error:', e);
        }
      },
      fail(err) {
        console.log('upload fail:', err);
        wx.showToast({ title: '上传失败', icon: 'none' });
      },
      complete() {
        that.isCapturing = false;
        that.setData({ detecting: false });
      }
    });
  },

  cameraError() {
    wx.showModal({ title: '摄像头错误', content: '请允许使用摄像头权限', showCancel: false });
  },

  goBack() {
    wx.navigateBack();
  }
});
