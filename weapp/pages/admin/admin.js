// 管理后台 - 全部功能
const app = getApp();
const API = () => app.globalData.serverUrl;

Page({
  data: {
    currentTab: 'courses',
    loading: false,
    API: '',  // 将在 onShow 中设置
    classFbStatus: {},
    classStudentCount: {},

    // 课程
    courses: [],
    newCourseName: '',

    // 班级
    classes: [],
    newClassName: '',

    // 学生
    selectedStudentCourse: '',
    studentQuery: '',
    students: [],

    // 签到报告
    selectedReportCourse: '',
    report: {},


    // 通用
    courseList: []
  },

  onShow() {
    this.setData({ API: app.globalData.serverUrl });
    this.loadCourses();
    this.loadClasses();
    // 加载当前标签的数据
    if (this.data.currentTab === 'courses') this.loadCourses();
    else if (this.data.currentTab === 'classes') this.loadClasses();
    else if (this.data.currentTab === 'students' && this.data.students.length === 0) this.loadStudents();
    else if (this.data.currentTab === 'checkin' && this.data.selectedReportCourse) this.loadReport();
  },

  // ─── 标签切换 ───────────────────────────
  switchTab(e) {
    const tab = e.currentTarget.dataset.tab;
    this.setData({ currentTab: tab, loading: false });
    if (tab === 'courses') this.loadCourses();
    else if (tab === 'classes') this.loadClasses();
    else if (tab === 'students') this.loadStudents();
    else if (tab === 'students') this.loadStudents();
    else if (tab === 'checkin' && this.data.selectedReportCourse) this.loadReport();
  },

  // ═══════════════════════════════════════
  // 课程管理
  // ═══════════════════════════════════════
  loadCourses() {
    this.setData({ loading: true });
    wx.request({
      url: API() + '/api/meetings',
      success: (res) => {
        const courses = (res.data || []).map(function(c) {
          c._rate = c.participant_count > 0 ? Math.round((c.checked_in || 0) / c.participant_count * 100) : 0;
          return c;
        });
        this.setData({
          courses,
          courseList: courses.map(c => c.name),
          loading: false
        });
      },
      fail: () => this.setData({ loading: false })
    });
  },

  onNewCourseInput(e) {
    this.setData({ newCourseName: e.detail.value });
  },

  createCourse() {
    const name = this.data.newCourseName.trim();
    if (!name) { wx.showToast({ title: '请输入名称', icon: 'none' }); return; }
    wx.request({
      url: API() + '/api/meetings',
      method: 'POST',
      header: { 'Content-Type': 'application/json' },
      data: { name, description: '' },
      success: (res) => {
        if (res.statusCode === 201) {
          wx.showToast({ title: '创建成功', icon: 'success' });
          this.setData({ newCourseName: '' });
          this.loadCourses();
        } else {
          wx.showToast({ title: res.data?.error || '创建失败', icon: 'none' });
        }
      }
    });
  },

  onCourseTap(e) {
    const name = e.currentTarget.dataset.name;
    const that = this;
    wx.showActionSheet({
      itemList: ['📋 查看详情/报告', '🏢 关联班级', '✏️ 重命名', '🗑 删除'],
      success(res) {
        if (res.tapIndex === 0) {
          wx.setClipboardData({
            data: API() + '/meeting/' + encodeURIComponent(name),
            success: () => wx.showToast({ title: '报告链接已复制', icon: 'success' })
          });
        } else if (res.tapIndex === 1) {
          that.manageCourseClasses(name);
        } else if (res.tapIndex === 2) {
          wx.showModal({
            title: '重命名课程',
            editable: true,
            placeholderText: '新名称',
            success: (modal) => {
              if (modal.confirm && modal.content) {
                wx.request({
                  url: API() + '/api/meeting/' + encodeURIComponent(name) + '/rename',
                  method: 'POST',
                  header: { 'Content-Type': 'application/json' },
                  data: { new_name: modal.content.trim() },
                  success: () => {
                    wx.showToast({ title: '已重命名', icon: 'success' });
                    that.loadCourses();
                  }
                });
              }
            }
          });
        } else if (res.tapIndex === 3) {
          wx.showModal({
            title: '删除课程',
            content: '确定删除"' + name + '"吗？所有数据将丢失！',
            success: (modal) => {
              if (modal.confirm) {
                wx.request({
                  url: API() + '/api/meeting/' + encodeURIComponent(name),
                  method: 'DELETE',
                  success: () => {
                    wx.showToast({ title: '已删除', icon: 'success' });
                    that.loadCourses();
                  }
                });
              }
            }
          });
        }
      }
    });
  },

  manageCourseClasses(courseName) {
    const that = this;
    // 加载课程当前关联的班级和所有全局班级
    wx.request({
      url: API() + '/api/course/' + encodeURIComponent(courseName) + '/classes',
      success(r1) {
        const current = r1.data?.classes || [];
        wx.request({
          url: API() + '/api/global-classes',
          success(r2) {
            const all = r2.data?.classes || [];
            if (!all.length) {
              wx.showToast({ title: '暂无可用班级', icon: 'none' });
              return;
            }
            // 构建选择列表：已关联的默认选中
            const items = all.map(function(c) {
              return (current.indexOf(c) >= 0 ? '✅ ' : '') + c;
            });
            wx.showActionSheet({
              itemList: items,
              success(act) {
                const clicked = all[act.tapIndex];
                let newClasses = current.slice();
                const idx = newClasses.indexOf(clicked);
                if (idx >= 0) {
                  newClasses.splice(idx, 1); // 取消关联
                } else {
                  newClasses.push(clicked); // 关联
                }
                // 保存
                wx.showLoading({ title: '保存中...' });
                wx.request({
                  url: API() + '/api/course/' + encodeURIComponent(courseName) + '/classes',
                  method: 'POST',
                  header: { 'Content-Type': 'application/json' },
                  data: { classes: newClasses },
                  success(r3) {
                    wx.hideLoading();
                    wx.showToast({ title: '已更新班级关联', icon: 'success' });
                  },
                  fail() {
                    wx.hideLoading();
                    wx.showToast({ title: '保存失败', icon: 'none' });
                  }
                });
              }
            });
          }
        });
      }
    });
  },

  // ═══════════════════════════════════════
  // 班级管理
  // ═══════════════════════════════════════
  loadClasses() {
    this.setData({ loading: true });
    const that = this;
    wx.request({
      url: API() + '/api/global-classes',
      success: (res) => {
        const classes = res.data?.classes || [];
        that.setData({ classes, loading: false });
        // 加载每个班级的学生数和特征库状态
        classes.forEach(function(c) {
          wx.request({
            url: API() + '/api/class/' + encodeURIComponent(c) + '/students',
            success(r2) {
              const students = r2.data?.students || [];
              that.setData({ ['classStudentCount.' + c]: students.length });
            }
          });
          wx.request({
            url: API() + '/api/class/' + encodeURIComponent(c) + '/build-facebank',
            success(r3) {
              if (r3.data && r3.data.built) {
                that.setData({ ['classFbStatus.' + c]: r3.data.count + ' 人' });
              }
            }
          });
        });
      },
      fail: () => this.setData({ loading: false })
    });
  },

  onNewClassInput(e) {
    this.setData({ newClassName: e.detail.value });
  },

  createClass() {
    const name = this.data.newClassName.trim();
    if (!name) { wx.showToast({ title: '请输入名称', icon: 'none' }); return; }
    wx.request({
      url: API() + '/api/global-classes',
      method: 'POST',
      header: { 'Content-Type': 'application/json' },
      data: { name },
      success: (res) => {
        if (res.data?.success) {
          wx.showToast({ title: '创建成功', icon: 'success' });
          this.setData({ newClassName: '' });
          this.loadClasses();
        } else {
          wx.showToast({ title: res.data?.error || '失败', icon: 'none' });
        }
      }
    });
  },

  deleteClass(e) {
    const name = e.currentTarget.dataset.name;
    wx.showModal({
      title: '删除班级',
      content: '删除"' + name + '"? 相关学生将被清除。',
      success: (res) => {
        if (res.confirm) {
          wx.request({
            url: API() + '/api/global-classes/' + encodeURIComponent(name),
            method: 'DELETE',
            success: () => {
              wx.showToast({ title: '已删除', icon: 'success' });
              this.loadClasses();
            }
          });
        }
      }
    });
  },

  buildClassFacebank(e) {
    const name = e.currentTarget.dataset.name;
    const that = this;
    wx.showLoading({ title: '构建班级特征库...' });
    wx.request({
      url: API() + '/api/class/' + encodeURIComponent(name) + '/build-facebank',
      method: 'POST',
      success(res) {
        wx.hideLoading();
        if (res.data?.success) {
          const count = res.data.count || 0;
          wx.showToast({ title: '构建完成 ' + count + ' 人', icon: 'success' });
          that.setData({ ['classFbStatus.' + name]: count + ' 人' });
        } else {
          wx.showToast({ title: res.data?.error || '失败', icon: 'none' });
        }
      },
      fail() {
        wx.hideLoading();
        wx.showToast({ title: '网络错误', icon: 'none' });
      }
    });
  },

  // ═══════════════════════════════════════
  // 学生管理
  // ═══════════════════════════════════════
  loadStudents() {
    this.setData({ loading: true });
    wx.request({
      url: API() + '/api/global/students',
      success: (res) => {
        let data = res.data?.students || [];
        const q = this.data.studentQuery.toLowerCase();
        if (q) {
          data = data.filter(function(s) { return s.name.toLowerCase().includes(q); });
        }
        this.setData({ students: data, loading: false });
      },
      fail: () => this.setData({ loading: false })
    });
  },

  onSearchStudent(e) {
    this.setData({ studentQuery: e.detail.value });
    this.loadStudents();
  },

  showAddStudent() {
    const that = this;
    wx.showActionSheet({
      itemList: ['📝 手动添加', '📱 扫码自主注册'],
      success(act) {
        if (act.tapIndex === 0) {
          that._manualAddStudent();
        } else {
          that.showRegQR();
        }
      }
    });
  },

  _manualAddStudent() {
    const that = this;
    // 先输入姓名
    wx.showModal({
      title: '学生姓名',
      editable: true,
      placeholderText: '输入姓名',
      success(modal) {
        if (!modal.confirm || !modal.content) return;
        const name = modal.content.trim();
        // 选择班级
        wx.request({
          url: API() + '/api/global-classes',
          success(clsRes) {
            const classes = clsRes.data?.classes || [];
            if (classes.length === 0) {
              that.saveGlobalStudent(name, '', '');
            } else {
              wx.showActionSheet({
                itemList: ['无班级'].concat(classes),
                success(act) {
                  const selClass = act.tapIndex === 0 ? '' : classes[act.tapIndex - 1];
                  // 输入电话
                  wx.showModal({
                    title: '电话（选填）',
                    editable: true,
                    placeholderText: '电话号码',
                    success(phoneModal) {
                      const phone = phoneModal.confirm ? phoneModal.content.trim() : '';
                      // 先保存学生信息
                      that.saveGlobalStudent(name, selClass, phone);
                    }
                  });
                },
                fail() { that.saveGlobalStudent(name, '', ''); }
              });
            }
          },
          fail() { that.saveGlobalStudent(name, '', ''); }
        });
      }
    });
  },

  saveGlobalStudent(name, className, phone) {
    const that = this;
    wx.showLoading({ title: '保存中...' });
    wx.request({
      url: API() + '/api/global/students',
      method: 'POST',
      header: { 'Content-Type': 'application/json' },
      data: { name: name, class: className, phone: phone },
      success(res) {
        wx.hideLoading();
        if (res.statusCode === 201 || res.data?.success) {
          // 询问是否添加照片
          wx.showModal({
            title: '添加照片？',
            content: '是否为此学生拍摄或选择照片？',
            success(modal) {
              if (modal.confirm) {
                that.uploadStudentPhoto(name);
              } else {
                wx.showToast({ title: '添加成功', icon: 'success' });
                that.loadStudents();
              }
            },
            fail() {
              wx.showToast({ title: '添加成功', icon: 'success' });
              that.loadStudents();
            }
          });
        } else {
          wx.showToast({ title: res.data?.error || '失败', icon: 'none' });
        }
      },
      fail() { wx.hideLoading(); wx.showToast({ title: '网络错误', icon: 'none' }); }
    });
  },

  uploadStudentPhoto(name) {
    const that = this;
    wx.showActionSheet({
      itemList: ['拍照', '从相册选择'],
      success(res) {
        const source = res.tapIndex === 0 ? 'camera' : 'album';
        wx.chooseMedia({
          count: 1, mediaType: ['image'], sourceType: [source],
          success(media) {
            wx.showLoading({ title: '上传中...' });
            wx.uploadFile({
              url: API() + '/api/global/students/' + encodeURIComponent(name) + '/photo',
              filePath: media.tempFiles[0].tempFilePath,
              name: 'photo',
              success() {
                wx.hideLoading();
                wx.showToast({ title: '添加成功', icon: 'success' });
                that.loadStudents();
              },
              fail() {
                wx.hideLoading();
                wx.showToast({ title: '上传失败', icon: 'none' });
                that.loadStudents();
              }
            });
          },
          fail() {
            wx.showToast({ title: '添加成功', icon: 'success' });
            that.loadStudents();
          }
        });
      },
      fail() {
        wx.showToast({ title: '添加成功', icon: 'success' });
        that.loadStudents();
      }
    });
  },

  showRegQR() {
    const that = this;
    // 先获取所有全局班级
    wx.request({
      url: API() + '/api/global-classes',
      success(res) {
        const classes = res.data?.classes || [];
        if (!classes.length) {
          wx.showToast({ title: '暂无班级，请先创建', icon: 'none' });
          return;
        }
        wx.showActionSheet({
          itemList: classes,
          success(act) {
            that._showQRForClass(classes[act.tapIndex]);
          }
        });
      },
      fail() {
        wx.showToast({ title: '加载班级失败', icon: 'none' });
      }
    });
  },

  _showQRForClass(className) {
    const baseUrl = app.globalData.serverUrl;
    const regUrl = baseUrl + '/register/class/' + encodeURIComponent(className);
    const qrUrl = 'https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=' + encodeURIComponent(regUrl);
    wx.setClipboardData({
      data: regUrl,
      success() {
        wx.showToast({ title: '注册链接已复制', icon: 'success' });
      }
    });
    wx.previewImage({
      urls: [qrUrl],
      current: qrUrl
    });
  },

  deleteStudent(e) {
    const name = e.currentTarget.dataset.name;
    wx.showModal({
      title: '删除学生',
      content: '确定从全局删除"' + name + '"?\n（课程中的照片记录不受影响）',
      success: (res) => {
        if (res.confirm) {
          wx.request({
            url: API() + '/api/global/students/' + encodeURIComponent(name),
            method: 'DELETE',
            success: () => {
              wx.showToast({ title: '已删除', icon: 'success' });
              this.loadStudents();
            },
            fail: () => wx.showToast({ title: '删除失败', icon: 'none' })
          });
        }
      }
    });
  },

  onStudentTap(e) {
    const ds = e.currentTarget.dataset;
    const name = ds.name;
    const dept = ds.dept;
    const phone = ds.phone;
    const that = this;

    wx.showActionSheet({
      itemList: ['✏️ 编辑信息', '🗑 删除'],
      success(res) {
        if (res.tapIndex === 0) {
          // 第一步：编辑姓名
          wx.showModal({
            title: '编辑姓名',
            editable: true,
            content: name,
            placeholderText: '学生姓名',
            success(modal1) {
              const newName = (modal1.confirm && modal1.content) ? modal1.content.trim() : name;
              // 第二步：选择班级
              wx.request({
                url: API() + '/api/global-classes',
                success(clsRes) {
                  const allClasses = clsRes.data?.classes || [];
                  const items = ['不修改'].concat(allClasses);
                  wx.showActionSheet({
                    itemList: items,
                    success(act) {
                      const newDept = act.tapIndex === 0 ? dept : allClasses[act.tapIndex - 1];
                      // 第三步：编辑电话
                      wx.showModal({
                        title: '编辑电话',
                        editable: true,
                        content: phone || '',
                        placeholderText: '电话号码',
                        success(modal3) {
                          const newPhone = (modal3.confirm && modal3.content !== undefined) ? modal3.content.trim() : phone;
                          // 保存到全局
                          wx.showLoading({ title: '保存中...' });
                          wx.request({
                            url: API() + '/api/global/students',
                            method: 'POST',
                            header: { 'Content-Type': 'application/json' },
                            data: { name: newName, class: newDept, phone: newPhone },
                            success() {
                              wx.hideLoading();
                              wx.showToast({ title: '已保存', icon: 'success' });
                              that.loadStudents();
                            },
                            fail() {
                              wx.hideLoading();
                              wx.showToast({ title: '保存失败', icon: 'none' });
                            }
                          });
                        }
                      });
                    }
                  });
                },
                fail() {
                  // 无法加载班级列表，跳过班级修改
                  wx.showModal({ title: '编辑电话', editable: true, content: phone || '', placeholderText: '电话',
                    success(modal3) {
                      const np = modal3.confirm ? modal3.content.trim() : phone;
                      that._saveGlobal(newName, dept, np);
                    }
                  });
                }
              });
            }
          });
        } else if (res.tapIndex === 1) {
          that.deleteStudent({ currentTarget: { dataset: { name } } });
        }
      }
    });
  },

  _saveGlobal(name, cls, phone) {
    const that = this;
    wx.showLoading({ title: '保存中...' });
    wx.request({
      url: API() + '/api/global/students',
      method: 'POST', header: { 'Content-Type': 'application/json' },
      data: { name: name, class: cls, phone: phone },
      success() { wx.hideLoading(); wx.showToast({ title: '已保存', icon: 'success' }); that.loadStudents(); },
      fail() { wx.hideLoading(); wx.showToast({ title: '保存失败', icon: 'none' }); }
    });
  },

  // ═══════════════════════════════════════
  // 签到管理
  // ═══════════════════════════════════════
  onReportCourseChange(e) {
    const course = this.data.courseList[e.detail.value];
    this.setData({ selectedReportCourse: course });
    this.loadReport();
  },

  loadReport() {
    const course = this.data.selectedReportCourse;
    if (!course) return;
    this.setData({ loading: true });
    wx.request({
      url: API() + '/api/mobile/checkin/result?course=' + encodeURIComponent(course),
      success: (res) => {
        const d = res.data || {};
        // 转换为与 report 兼容的格式
        this.setData({
          report: {
            total_participants: d.total || 0,
            checked_in: d.checked_in || 0,
            not_checked_in: (d.total || 0) - (d.checked_in || 0),
            checkin_rate: d.rate || '0%',
            records: d.records || []
          },
          loading: false
        });
      },
      fail: () => this.setData({ loading: false })
    });
  },

  goDetect() {
    wx.navigateTo({
      url: '/pages/detect/detect'
    });
  }
});