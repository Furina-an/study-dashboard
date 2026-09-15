<template>
  <div class="page">
    <h1>课表</h1>
    <p class="date-line">按节次排课，支持 AI 解析、Excel / CSV 导入与手动录入，一键把课程变成带截止日期的任务。</p>

    <div class="filter-tabs page-tabs">
      <button class="chip" :class="{ active: tab === 'grid' }" @click="tab = 'grid'">📋 周视图</button>
      <button class="chip" :class="{ active: tab === 'settings' }" @click="tab = 'settings'">⚙️ 学期与作息</button>
    </div>

    <p v-if="error || timetable.error" class="banner error">{{ error || timetable.error }}</p>
    <p v-if="notice" class="banner info">{{ notice }}</p>

    <section v-if="tab === 'grid'" class="panel">
      <div class="panel-head">
        <h2>第 {{ viewWeek }} 周</h2>
        <button class="btn small" @click="shiftWeek(-1)">‹ 上一周</button>
        <button class="btn small" @click="shiftWeek(1)">下一周 ›</button>
        <button class="btn small ghost" @click="goCurrentWeek">回到本周</button>
        <span class="filter-gap"></span>
        <button class="btn small" @click="openImport('manual')">＋ 添加课程</button>
        <button class="btn small" @click="openImport('ai')">📥 导入课表</button>
        <button class="btn small primary" :disabled="busy" @click="generateAll">
          {{ busy ? '处理中…' : '⚡ 生成上课任务' }}
        </button>
      </div>
      <p class="muted small">
        共 {{ timetable.courses.length }} 门课，本周 {{ weekCourses.length }} 节；点击课程卡片可编辑、删除或生成任务，点击空格可快速添加。
      </p>
      <div v-if="!timetable.termStart" class="banner info">
        还没设置「学期第 1 周周一」：导入与展示不受影响，只有生成任务需要先设置。
      </div>
      <div class="tt-scroll">
        <div class="tt-grid" :style="gridStyle">
          <div class="tt-corner" :style="cellStyle(1, 1)">节次</div>
          <div
            v-for="(label, index) in WEEKDAY_LABELS"
            :key="label"
            class="tt-head"
            :class="{ 'tt-head-today': isTodayColumn(index + 1) }"
            :style="cellStyle(1, index + 2)"
          >
            {{ label }}
          </div>
          <template v-for="slot in periods" :key="slot.index">
            <div class="tt-time" :style="cellStyle(slot.index + 1, 1)">
              <strong>第 {{ slot.index }} 节</strong>
              <span>{{ slot.start }}</span>
            </div>
            <div
              v-for="day in 7"
              :key="day"
              class="tt-cell"
              :class="{ 'tt-today': isTodayColumn(day) }"
              :style="cellStyle(slot.index + 1, day + 1)"
              @click="quickAdd(day, slot.index)"
            ></div>
          </template>
          <button
            v-for="course in weekCourses"
            :key="course.id"
            class="tt-course"
            :style="courseStyle(course)"
            @click="openEdit(course)"
          >
            <span class="tt-course-name">{{ course.name }}</span>
            <span v-if="course.location" class="tt-course-meta">@{{ course.location }}</span>
            <span v-else-if="course.teacher" class="tt-course-meta">{{ course.teacher }}</span>
          </button>
        </div>
      </div>
      <p v-if="!timetable.courses.length" class="muted">还没有课程，点「导入课表」开始吧。</p>
    </section>

    <section v-else class="panel">
      <div class="panel-head">
        <h2>学期与作息时间</h2>
        <button class="btn small ghost" @click="resetPeriods">恢复默认作息</button>
        <span class="filter-gap"></span>
        <button class="btn small primary" :disabled="busy" @click="saveSettings">保存设置</button>
      </div>
      <div class="grid-2">
        <label class="field">
          <span>学期第 1 周周一</span>
          <input v-model="settingsDraft.term_start" class="input" type="date" />
        </label>
        <label class="field">
          <span>总周数（1-30）</span>
          <input v-model.number="settingsDraft.total_weeks" class="input" type="number" min="1" max="30" />
        </label>
      </div>
      <h3>作息表</h3>
      <p class="muted small">时间格式 HH:MM；导入表格里若只有时间（如 08:00-09:40），会按这里的作息反查节次。</p>
      <table class="tt-table">
        <thead>
          <tr><th>节次</th><th>开始</th><th>结束</th><th></th></tr>
        </thead>
        <tbody>
          <tr v-for="(slot, index) in settingsDraft.periods" :key="index">
            <td>第 {{ index + 1 }} 节</td>
            <td><input v-model="slot.start" class="input" type="time" /></td>
            <td><input v-model="slot.end" class="input" type="time" /></td>
            <td><button class="btn small danger" @click="removeSlot(index)">删除</button></td>
          </tr>
        </tbody>
      </table>
      <button class="btn small" @click="addSlot">＋ 增加一节</button>
    </section>

    <div v-if="editing" class="modal-backdrop" @click.self="editing = null">
      <div class="modal">
        <h2>编辑课程</h2>
        <label class="field"><span>课程名</span><input v-model="editDraft.name" class="input" /></label>
        <div class="grid-2">
          <label class="field"><span>星期</span>
            <select v-model.number="editDraft.weekday" class="input">
              <option v-for="(label, index) in WEEKDAY_LABELS" :key="label" :value="index + 1">{{ label }}</option>
            </select>
          </label>
          <label class="field"><span>节次（起 / 止）</span>
            <span class="input-row">
              <input v-model.number="editDraft.start_period" class="input narrow" type="number" min="1" max="30" />
              <input v-model.number="editDraft.end_period" class="input narrow" type="number" min="1" max="30" />
            </span>
          </label>
          <label class="field"><span>教师</span><input v-model="editDraft.teacher" class="input" /></label>
          <label class="field"><span>地点</span><input v-model="editDraft.location" class="input" /></label>
          <label class="field"><span>生效周次（1-16 或 1,3,5；留空=全学期）</span>
            <input v-model="editDraft.weeksText" class="input" />
          </label>
          <label class="field"><span>颜色</span><input v-model="editDraft.color" class="input" type="color" /></label>
        </div>
        <label class="field"><span>备注</span><input v-model="editDraft.note" class="input" /></label>
        <p v-if="modalError" class="error-text">{{ modalError }}</p>
        <div class="modal-actions">
          <button class="btn small danger" @click="removeEditing">删除</button>
          <button class="btn small ghost" @click="generateOne">生成任务</button>
          <button class="btn small" @click="editing = null">取消</button>
          <button class="btn small primary" :disabled="busy" @click="saveEditing">保存</button>
        </div>
      </div>
    </div>

    <div v-if="importOpen" class="modal-backdrop" @click.self="closeImport">
      <div class="modal wide">
        <h2>导入课表</h2>
        <div class="filter-tabs">
          <button class="chip" :class="{ active: importTab === 'ai' }" @click="importTab = 'ai'">🤖 AI 解析</button>
          <button class="chip" :class="{ active: importTab === 'excel' }" @click="importTab = 'excel'">📄 Excel / CSV</button>
          <button class="chip" :class="{ active: importTab === 'manual' }" @click="importTab = 'manual'">✍️ 手动添加</button>
        </div>

        <template v-if="importTab === 'ai'">
          <p class="muted small">把教务系统里的课表文本整段粘贴过来，AI 会解析成结构化课程（需先在「AI 设置」配置 API）。</p>
          <textarea
            v-model="aiText"
            class="input"
            rows="5"
            placeholder="高等数学 周一 1-2节 1-16周 张老师 教三301"
          ></textarea>
          <button class="btn small primary" :disabled="busy || !aiText.trim()" @click="runAiParse">
            {{ busy ? '解析中…' : '开始解析' }}
          </button>
        </template>

        <template v-else-if="importTab === 'excel'">
          <p class="muted small">支持 .xlsx 与 .csv（旧版 .xls 请先另存）。上传后自动识别表头，可手动改列映射再解析。</p>
          <input class="input" type="file" accept=".xlsx,.csv" @change="onFile" />
          <div v-if="headers.length" class="tt-mapping">
            <label v-for="field in MAPPING_FIELDS" :key="field.key" class="field">
              <span>{{ field.label }}</span>
              <select v-model="mapping[field.key]" class="input">
                <option :value="undefined">不使用</option>
                <option v-for="(header, index) in headers" :key="`${header}-${index}`" :value="index">
                  {{ header || `第 ${index + 1} 列` }}
                </option>
              </select>
            </label>
            <button class="btn small primary" :disabled="busy" @click="runRowParse">按映射解析</button>
          </div>
        </template>

        <template v-else>
          <div class="grid-2">
            <label class="field"><span>课程名 *</span><input v-model="manual.name" class="input" /></label>
            <label class="field"><span>星期</span>
              <select v-model.number="manual.weekday" class="input">
                <option v-for="(label, index) in WEEKDAY_LABELS" :key="label" :value="index + 1">{{ label }}</option>
              </select>
            </label>
            <label class="field"><span>节次（起 / 止）</span>
              <span class="input-row">
                <input v-model.number="manual.start_period" class="input narrow" type="number" min="1" max="30" />
                <input v-model.number="manual.end_period" class="input narrow" type="number" min="1" max="30" />
              </span>
            </label>
            <label class="field"><span>生效周次</span><input v-model="manual.weeksText" class="input" placeholder="1-16" /></label>
            <label class="field"><span>教师</span><input v-model="manual.teacher" class="input" /></label>
            <label class="field"><span>地点</span><input v-model="manual.location" class="input" /></label>
          </div>
          <button class="btn small" @click="addManualRow">加到预览</button>
        </template>

        <p v-if="previewWarnings.length" class="tt-warnings">
          <span v-for="(warning, index) in previewWarnings" :key="index" class="tag tag-due">{{ warning }}</span>
        </p>

        <template v-if="preview.length">
          <h3>预览（{{ preview.length }} 条，可直接修改）</h3>
          <div class="tt-preview-scroll">
            <table class="tt-table">
              <thead>
                <tr>
                  <th>课程名</th><th>星期</th><th>起</th><th>止</th><th>周次</th><th>教师</th><th>地点</th><th></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, index) in preview" :key="index">
                  <td><input v-model="row.name" class="input" /></td>
                  <td>
                    <select v-model.number="row.weekday" class="input">
                      <option v-for="(label, i) in WEEKDAY_LABELS" :key="label" :value="i + 1">{{ label }}</option>
                    </select>
                  </td>
                  <td><input v-model.number="row.start_period" class="input narrow" type="number" min="1" max="30" /></td>
                  <td><input v-model.number="row.end_period" class="input narrow" type="number" min="1" max="30" /></td>
                  <td><input v-model="row.weeksText" class="input" placeholder="1-16" /></td>
                  <td><input v-model="row.teacher" class="input" /></td>
                  <td><input v-model="row.location" class="input" /></td>
                  <td><button class="btn small ghost" @click="preview.splice(index, 1)">✕</button></td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-if="modalError" class="error-text">{{ modalError }}</p>
          <div class="modal-actions">
            <label class="tt-replace">
              <input v-model="replaceAll" type="checkbox" /> 覆盖原有课表
            </label>
            <span class="filter-gap"></span>
            <button class="btn small" @click="closeImport">取消</button>
            <button class="btn small primary" :disabled="busy" @click="commitImport">
              {{ busy ? '保存中…' : `确认导入 ${preview.length} 条` }}
            </button>
          </div>
        </template>
        <div v-else class="modal-actions">
          <p v-if="modalError" class="error-text">{{ modalError }}</p>
          <button class="btn small" @click="closeImport">关闭</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { api } from '../api'
import {
  WEEKDAY_LABELS,
  courseColor,
  formatWeeks,
  parseWeeksText,
  useTimetableStore,
} from '../stores/timetable'

const DEFAULT_PERIODS = [
  { index: 1, start: '08:00', end: '08:45' },
  { index: 2, start: '08:55', end: '09:40' },
  { index: 3, start: '10:00', end: '10:45' },
  { index: 4, start: '10:55', end: '11:40' },
  { index: 5, start: '14:00', end: '14:45' },
  { index: 6, start: '14:55', end: '15:40' },
  { index: 7, start: '16:00', end: '16:45' },
  { index: 8, start: '16:55', end: '17:40' },
  { index: 9, start: '19:00', end: '19:45' },
  { index: 10, start: '19:55', end: '20:40' },
  { index: 11, start: '20:50', end: '21:35' },
  { index: 12, start: '21:45', end: '22:30' },
]

const MAPPING_FIELDS = [
  { key: 'name', label: '课程名' },
  { key: 'weekday', label: '星期' },
  { key: 'periods', label: '节次' },
  { key: 'time', label: '上课时间' },
  { key: 'weeks', label: '周次' },
  { key: 'teacher', label: '教师' },
  { key: 'location', label: '地点' },
]

const timetable = useTimetableStore()

const tab = ref('grid')
const busy = ref(false)
const error = ref('')
const notice = ref('')
const modalError = ref('')
const viewWeek = ref(1)

const periods = computed(() =>
  timetable.periods.length ? timetable.periods : DEFAULT_PERIODS.map((slot) => ({ ...slot }))
)

const todayWeekday = computed(() => {
  const day = new Date().getDay()
  return day === 0 ? 7 : day
})

const gridStyle = computed(() => ({
  gridTemplateRows: `auto repeat(${periods.value.length}, minmax(62px, auto))`,
}))

function cellStyle(row, column) {
  return { gridRow: `${row}`, gridColumn: `${column}` }
}

function courseStyle(course) {
  const total = periods.value.length
  const start = Math.min(Math.max(course.start_period || 1, 1), total)
  const end = Math.min(Math.max(course.end_period || start, start), total)
  return {
    gridRow: `${start + 1} / span ${end - start + 1}`,
    gridColumn: `${course.weekday + 1}`,
    '--course-color': courseColor(course),
  }
}

const weekCourses = computed(() =>
  timetable.courses.filter(
    (course) => !course.weeks?.length || course.weeks.includes(viewWeek.value)
  )
)

function isTodayColumn(day) {
  return Boolean(timetable.currentWeek) && viewWeek.value === timetable.currentWeek && day === todayWeekday.value
}

function shiftWeek(delta) {
  const next = viewWeek.value + delta
  viewWeek.value = Math.min(Math.max(next, 1), timetable.totalWeeks)
}

function goCurrentWeek() {
  viewWeek.value = timetable.currentWeek || 1
}

// ---------------- 学期与作息 ----------------

const settingsDraft = reactive({ term_start: '', total_weeks: 16, periods: [] })

function syncSettingsDraft() {
  settingsDraft.term_start = timetable.termStart
  settingsDraft.total_weeks = timetable.totalWeeks
  settingsDraft.periods = periods.value.map((slot) => ({ ...slot }))
}

function plusMinutes(time, minutes) {
  const [hour, minute] = String(time || '08:00').split(':').map((item) => parseInt(item, 10))
  const total = (hour || 8) * 60 + (minute || 0) + minutes
  const wrapped = ((total % 1440) + 1440) % 1440
  return `${String(Math.floor(wrapped / 60)).padStart(2, '0')}:${String(wrapped % 60).padStart(2, '0')}`
}

function addSlot() {
  const last = settingsDraft.periods[settingsDraft.periods.length - 1]
  const start = last ? last.end : '08:00'
  settingsDraft.periods.push({ index: settingsDraft.periods.length + 1, start, end: plusMinutes(start, 45) })
}

function removeSlot(index) {
  if (settingsDraft.periods.length <= 1) return
  settingsDraft.periods.splice(index, 1)
}

function resetPeriods() {
  settingsDraft.periods = DEFAULT_PERIODS.map((slot) => ({ ...slot }))
}

async function saveSettings() {
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    await timetable.saveSettings({
      term_start: settingsDraft.term_start || null,
      total_weeks: Number(settingsDraft.total_weeks) || 16,
      periods: settingsDraft.periods.map((slot, index) => ({
        index: index + 1,
        start: slot.start,
        end: slot.end,
      })),
    })
    syncSettingsDraft()
    viewWeek.value = Math.min(viewWeek.value, timetable.totalWeeks)
    notice.value = '设置已保存'
  } catch (err) {
    error.value = err.message
  } finally {
    busy.value = false
  }
}

// ---------------- 编辑单门课程 ----------------

const editing = ref(null)
const editDraft = reactive({
  name: '',
  teacher: '',
  location: '',
  weekday: 1,
  start_period: 1,
  end_period: 1,
  weeksText: '',
  color: '',
  note: '',
})

function openEdit(course) {
  editing.value = course
  modalError.value = ''
  Object.assign(editDraft, {
    name: course.name,
    teacher: course.teacher || '',
    location: course.location || '',
    weekday: course.weekday,
    start_period: course.start_period,
    end_period: course.end_period,
    weeksText: formatWeeks(course.weeks),
    color: course.color || courseColor(course),
    note: course.note || '',
  })
}

function clampPeriod(value, fallback) {
  const number = parseInt(value, 10)
  if (Number.isNaN(number)) return fallback
  return Math.min(Math.max(number, 1), 30)
}

async function saveEditing() {
  busy.value = true
  modalError.value = ''
  const start = clampPeriod(editDraft.start_period, 1)
  try {
    await timetable.updateCourse(editing.value.id, {
      name: editDraft.name.trim(),
      teacher: editDraft.teacher.trim(),
      location: editDraft.location.trim(),
      weekday: clampPeriod(editDraft.weekday, 1),
      start_period: start,
      end_period: Math.max(start, clampPeriod(editDraft.end_period, start)),
      weeks: parseWeeksText(editDraft.weeksText),
      color: editDraft.color.trim(),
      note: editDraft.note.trim(),
    })
    editing.value = null
    notice.value = '课程已更新'
  } catch (err) {
    modalError.value = err.message
  } finally {
    busy.value = false
  }
}

async function removeEditing() {
  if (!window.confirm(`确定删除「${editing.value.name}」吗？`)) return
  busy.value = true
  try {
    await timetable.removeCourse(editing.value.id)
    editing.value = null
    notice.value = '课程已删除'
  } catch (err) {
    modalError.value = err.message
  } finally {
    busy.value = false
  }
}

async function generateOne() {
  busy.value = true
  modalError.value = ''
  try {
    const result = await api.generateCourseTasks(editing.value.id)
    notice.value = result.message
    editing.value = null
  } catch (err) {
    modalError.value = err.message
  } finally {
    busy.value = false
  }
}

async function generateAll() {
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    const result = await api.generateAllCourseTasks()
    notice.value = result.message
  } catch (err) {
    error.value = err.message
  } finally {
    busy.value = false
  }
}

// ---------------- 导入 ----------------

const importOpen = ref(false)
const importTab = ref('ai')
const aiText = ref('')
const headers = ref([])
const fileRows = ref([])
const mapping = reactive({})
const preview = ref([])
const previewWarnings = ref([])
const replaceAll = ref(false)
const manual = reactive({
  name: '',
  teacher: '',
  location: '',
  weekday: 1,
  start_period: 1,
  end_period: 2,
  weeksText: '',
})

function openImport(tabName) {
  importTab.value = tabName
  importOpen.value = true
  modalError.value = ''
  if (tabName === 'manual') {
    preview.value = []
    previewWarnings.value = []
  }
}

function closeImport() {
  importOpen.value = false
  modalError.value = ''
}

function quickAdd(day, period) {
  manual.weekday = day
  manual.start_period = period
  manual.end_period = period
  preview.value = []
  openImport('manual')
}

function applyPreview(data) {
  preview.value = (data.courses || []).map((course) => ({
    name: course.name,
    teacher: course.teacher || '',
    location: course.location || '',
    weekday: course.weekday,
    start_period: course.start_period,
    end_period: course.end_period,
    weeksText: formatWeeks(course.weeks),
    color: course.color || '',
    note: course.note || '',
  }))
  previewWarnings.value = data.warnings || []
}

async function runAiParse() {
  busy.value = true
  modalError.value = ''
  try {
    applyPreview(await api.parseCourseText(aiText.value))
  } catch (err) {
    modalError.value = err.message
  } finally {
    busy.value = false
  }
}

async function onFile(event) {
  const file = event.target.files?.[0]
  if (!file) return
  busy.value = true
  modalError.value = ''
  previewWarnings.value = []
  try {
    const data = await api.parseCourseFile(file)
    headers.value = data.headers
    fileRows.value = data.rows
    Object.keys(mapping).forEach((key) => delete mapping[key])
    Object.entries(data.suggested_mapping || {}).forEach(([key, value]) => {
      mapping[key] = value
    })
    if (data.truncated) {
      previewWarnings.value = [`文件较大，只读取前 ${data.rows.length} 行`]
    }
  } catch (err) {
    modalError.value = err.message
  } finally {
    busy.value = false
  }
}

async function runRowParse() {
  busy.value = true
  modalError.value = ''
  try {
    applyPreview(await api.parseCourseRows(fileRows.value, { ...mapping }))
  } catch (err) {
    modalError.value = err.message
  } finally {
    busy.value = false
  }
}

function addManualRow() {
  if (!manual.name.trim()) {
    modalError.value = '请先填写课程名'
    return
  }
  const start = clampPeriod(manual.start_period, 1)
  preview.value.push({
    name: manual.name.trim(),
    teacher: manual.teacher.trim(),
    location: manual.location.trim(),
    weekday: clampPeriod(manual.weekday, 1),
    start_period: start,
    end_period: Math.max(start, clampPeriod(manual.end_period, start)),
    weeksText: manual.weeksText,
    color: '',
    note: '',
  })
  modalError.value = ''
  manual.name = ''
  manual.teacher = ''
  manual.location = ''
  manual.weeksText = ''
}

async function commitImport() {
  const payload = preview.value
    .filter((row) => String(row.name || '').trim())
    .map((row) => {
      const start = clampPeriod(row.start_period, 1)
      return {
        name: String(row.name).trim(),
        teacher: String(row.teacher || '').trim(),
        location: String(row.location || '').trim(),
        weekday: clampPeriod(row.weekday, 1),
        start_period: start,
        end_period: Math.max(start, clampPeriod(row.end_period, start)),
        weeks: parseWeeksText(row.weeksText),
        color: String(row.color || '').trim(),
        note: String(row.note || '').trim(),
      }
    })
  if (!payload.length) {
    modalError.value = '预览里还没有有效课程'
    return
  }
  busy.value = true
  modalError.value = ''
  try {
    await timetable.bulkSave(payload, replaceAll.value)
    notice.value = `已导入 ${payload.length} 条课程`
    closeImport()
  } catch (err) {
    modalError.value = err.message
  } finally {
    busy.value = false
  }
}

onMounted(async () => {
  await timetable.fetch()
  syncSettingsDraft()
  viewWeek.value = timetable.currentWeek || 1
})
</script>
