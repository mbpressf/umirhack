export const SIDEBAR_SECTIONS = [
  { id: "overview", label: "Обзор" },
  { id: "assistant", label: "AI-ассистент" },
  { id: "top", label: "Топ проблем" },
  { id: "topics", label: "Темы и события" },
  { id: "trends", label: "Тренды" },
  { id: "sources", label: "Источники" },
  { id: "geography", label: "География" },
  { id: "notebook", label: "Блокнот" },
  { id: "profile", label: "Профиль" },
  { id: "settings", label: "Настройки" },
  { id: "region", label: "Выбор региона" },
];

export const REGION_OPTIONS = [
  {
    id: "rostov",
    name: "Ростовская область",
    description: "Текущий выбранный регион.",
  },
  {
    id: "krasnodar",
    name: "Краснодарский край",
    description: "Доступен для выбора.",
  },
  {
    id: "tatarstan",
    name: "Республика Татарстан",
    description: "Доступен для выбора.",
  },
  {
    id: "moscow-oblast",
    name: "Московская область",
    description: "Доступен для выбора.",
  },
  {
    id: "leningrad-oblast",
    name: "Ленинградская область",
    description: "Доступен для выбора.",
  },
  {
    id: "spb",
    name: "Санкт-Петербург",
    description: "Доступен для выбора.",
  },
  {
    id: "sverdlovsk",
    name: "Свердловская область",
    description: "Доступен для выбора.",
  },
  {
    id: "novosibirsk",
    name: "Новосибирская область",
    description: "Доступен для выбора.",
  },
  {
    id: "primorye",
    name: "Приморский край",
    description: "Доступен для выбора.",
  },
];

const mkTopic = (topic) => ({
  periodLabel: "31 марта — 4 апреля",
  updatedAt: "2026-04-04T10:00:00+03:00",
  sourceTypes: ["СМИ", "Telegram", "ВКонтакте", "Официальный"],
  factors: {
    intensity: 72,
    coverage: 68,
    socialImpact: 79,
    officialGap: 57,
  },
  snippets: [
    "Сигналы подтверждаются несколькими независимыми публичными источниками.",
    "Тема имеет устойчивую динамику и требует межведомственной верификации.",
  ],
  sources: [
    { name: "DonDay Ростов", type: "СМИ", status: "СМИ", timestamp: "04.04 10:20" },
    { name: "Telegram: районный канал", type: "Telegram", status: "Пользовательский", timestamp: "04.04 09:50" },
    { name: "Профильное ведомство", type: "Официальный", status: "Официальный", timestamp: "04.04 08:40" },
  ],
  timeline: [
    { date: "01.04", event: "Первое устойчивое появление сигнала." },
    { date: "03.04", event: "Рост числа источников и повторяемости обращений." },
    { date: "04.04", event: "Тема закреплена в приоритетном мониторинге." },
  ],
  trend: [18, 25, 31, 36, 44, 51, 58],
  ...topic,
});

const TOP_PROBLEMS_ROSTOV = [
  mkTopic({
    id: "water-bataysk",
    rank: 1,
    title: "Перебои с водоснабжением в Батайске",
    summary:
      "Фиксируются повторяющиеся сигналы о снижении давления и локальных отключениях воды в нескольких микрорайонах.",
    sector: "ЖКХ",
    municipality: "Батайск",
    priority: "Критический",
    score: 92,
    whyTop:
      "Высокая частота обращений, широкий географический охват и расхождение между официальной позицией и жалобами жителей.",
    sourceCount: 18,
    officialSignal: true,
    contradiction: true,
    spamRisk: false,
    factors: { intensity: 95, coverage: 82, socialImpact: 94, officialGap: 88 },
    trend: [28, 34, 41, 46, 62, 70, 76],
  }),
  mkTopic({
    id: "tko-aksay",
    rank: 2,
    title: "Жалобы на вывоз ТКО в Аксайском районе",
    summary:
      "Поступают сигналы о нерегулярном вывозе ТКО и переполнении контейнерных площадок в ряде поселений.",
    sector: "ЖКХ",
    municipality: "Аксайский район",
    priority: "Высокий",
    score: 88,
    whyTop: "Рост обращений за 7 дней и повторяемость по нескольким независимым источникам.",
    sourceCount: 15,
    officialSignal: true,
    contradiction: false,
    spamRisk: false,
    factors: { intensity: 86, coverage: 84, socialImpact: 90, officialGap: 63 },
    trend: [22, 24, 31, 33, 47, 51, 58],
  }),
  mkTopic({
    id: "roads-rostov",
    rank: 3,
    title: "Пробки и ремонт дорог в Ростове-на-Дону",
    summary:
      "В информационном поле фиксируется рост сигналов о затруднении движения на участках дорожного ремонта.",
    sector: "Транспорт",
    municipality: "Ростов-на-Дону",
    priority: "Высокий",
    score: 85,
    whyTop: "Тема влияет на ежедневную мобильность и стабильно удерживается в повестке.",
    sourceCount: 21,
    officialSignal: true,
    contradiction: true,
    spamRisk: false,
    factors: { intensity: 83, coverage: 90, socialImpact: 87, officialGap: 74 },
    trend: [30, 29, 34, 41, 49, 54, 56],
  }),
  mkTopic({
    id: "clinic-taganrog",
    rank: 4,
    title: "Очереди в поликлинике в Таганроге",
    summary:
      "Сигналы указывают на увеличение времени ожидания приёма и диагностических процедур в утренние часы.",
    sector: "Здравоохранение",
    municipality: "Таганрог",
    priority: "Высокий",
    score: 83,
    whyTop: "Повторяемость жалоб и выраженный социальный эффект для жителей.",
    sourceCount: 14,
    officialSignal: true,
    contradiction: false,
    spamRisk: false,
    factors: { intensity: 78, coverage: 76, socialImpact: 89, officialGap: 58 },
    trend: [18, 26, 31, 35, 40, 47, 52],
  }),
  mkTopic({
    id: "electricity-shakhty",
    rank: 5,
    title: "Перебои с электричеством в Шахтах",
    summary:
      "В ряде микрорайонов фиксируются повторные кратковременные отключения электроэнергии.",
    sector: "ЖКХ",
    municipality: "Шахты",
    priority: "Высокий",
    score: 81,
    whyTop: "Накопление обращений в течение трёх дней и влияние на бытовые процессы.",
    sourceCount: 12,
    officialSignal: true,
    contradiction: false,
    spamRisk: false,
    factors: { intensity: 77, coverage: 72, socialImpact: 86, officialGap: 59 },
    trend: [14, 18, 24, 29, 34, 41, 44],
  }),
];

TOP_PROBLEMS_ROSTOV.push(
  mkTopic({
    id: "transport-complaints",
    rank: 6,
    title: "Жалобы на общественный транспорт в агломерации",
    summary:
      "Сигналы указывают на нерегулярность интервалов движения и переполненность отдельных маршрутов в часы пик.",
    sector: "Транспорт",
    municipality: "Ростов-на-Дону",
    priority: "Средний",
    score: 78,
    whyTop: "Устойчивая повторяемость по нескольким муниципальным точкам.",
    sourceCount: 19,
    officialSignal: false,
    contradiction: true,
    spamRisk: false,
    factors: { intensity: 75, coverage: 84, socialImpact: 80, officialGap: 72 },
    trend: [20, 22, 26, 31, 35, 39, 43],
  }),
  mkTopic({
    id: "smoke-azov",
    rank: 7,
    title: "Запах гари и задымление в ряде населённых пунктов",
    summary:
      "Фиксируется серия сообщений о запахе гари и снижении качества воздуха в отдельных муниципалитетах.",
    sector: "Экология/ЧС",
    municipality: "Азов",
    priority: "Средний",
    score: 76,
    whyTop: "Высокая чувствительность темы и многоканальное распространение сигналов.",
    sourceCount: 13,
    officialSignal: true,
    contradiction: true,
    spamRisk: true,
    factors: { intensity: 72, coverage: 68, socialImpact: 84, officialGap: 71 },
    trend: [9, 15, 19, 28, 34, 31, 37],
  }),
  mkTopic({
    id: "uk-tszh-volgodonsk",
    rank: 8,
    title: "Проблемы с работой УК/ТСЖ в Волгодонске",
    summary:
      "Обращения касаются качества обслуживания многоквартирных домов и сроков реагирования на заявки.",
    sector: "Благоустройство",
    municipality: "Волгодонск",
    priority: "Средний",
    score: 74,
    whyTop: "Стабильная повторяемость обращений на локальных площадках.",
    sourceCount: 11,
    officialSignal: false,
    contradiction: false,
    spamRisk: false,
    factors: { intensity: 70, coverage: 66, socialImpact: 79, officialGap: 60 },
    trend: [11, 12, 17, 22, 26, 28, 31],
  }),
  mkTopic({
    id: "heating-kamensk",
    rank: 9,
    title: "Авария на теплосетях в Каменске-Шахтинском",
    summary:
      "В публичном поле фиксируются сообщения о локальной аварийной ситуации на теплосетях и сроках восстановления.",
    sector: "ЖКХ",
    municipality: "Каменск-Шахтинский",
    priority: "Средний",
    score: 73,
    whyTop: "Наличие официального подтверждения и социальная значимость для жилого фонда.",
    sourceCount: 10,
    officialSignal: true,
    contradiction: false,
    spamRisk: false,
    factors: { intensity: 69, coverage: 61, socialImpact: 82, officialGap: 55 },
    trend: [6, 7, 9, 16, 24, 30, 29],
  }),
  mkTopic({
    id: "roads-salsk",
    rank: 10,
    title: "Жалобы на состояние дорог в Сальском районе",
    summary:
      "Поступают сигналы о локальных дефектах дорожного покрытия на участках с регулярным транспортным потоком.",
    sector: "Транспорт",
    municipality: "Сальский район",
    priority: "Средний",
    score: 71,
    whyTop: "Стабильное накопление обращений и влияние на безопасность движения.",
    sourceCount: 9,
    officialSignal: false,
    contradiction: false,
    spamRisk: false,
    factors: { intensity: 66, coverage: 58, socialImpact: 78, officialGap: 54 },
    trend: [8, 10, 13, 16, 21, 23, 26],
  }),
);

const EXTRA_TOPICS_ROSTOV = [
  mkTopic({
    id: "school-transport-semyk",
    rank: null,
    title: "Нагрузка на школьные автобусные маршруты",
    summary:
      "Отмечены сообщения о нехватке мест на отдельных маршрутах в утренние часы. Тема находится в зоне наблюдения.",
    sector: "Образование",
    municipality: "Семикаракорский район",
    priority: "Средний",
    score: 67,
    whyTop: "Растущая динамика по двум населённым пунктам.",
    sourceCount: 6,
    officialSignal: false,
    contradiction: false,
    spamRisk: false,
    factors: { intensity: 62, coverage: 55, socialImpact: 71, officialGap: 49 },
    trend: [4, 7, 11, 12, 15, 19, 21],
  }),
  mkTopic({
    id: "water-quality-krasny",
    rank: null,
    title: "Локальные обращения по качеству воды в Красном Сулине",
    summary:
      "Поступают обращения о временном изменении качества воды. Требуется дополнительная лабораторная верификация.",
    sector: "ЖКХ",
    municipality: "Красный Сулин",
    priority: "Средний",
    score: 65,
    whyTop: "Сигналы поступают из нескольких независимых площадок.",
    sourceCount: 7,
    officialSignal: true,
    contradiction: false,
    spamRisk: false,
    factors: { intensity: 58, coverage: 52, socialImpact: 73, officialGap: 46 },
    trend: [5, 8, 9, 11, 14, 15, 17],
  }),
  mkTopic({
    id: "fap-kagalnik",
    rank: null,
    title: "Сроки ремонта ФАПа в Кагальницком районе",
    summary:
      "Жители уточняют сроки завершения ремонта и доступность альтернативного приёма на период работ.",
    sector: "Здравоохранение",
    municipality: "Кагальницкий район",
    priority: "Наблюдение",
    score: 58,
    whyTop: "Стабильное количество обращений без резких всплесков.",
    sourceCount: 5,
    officialSignal: true,
    contradiction: false,
    spamRisk: false,
    factors: { intensity: 48, coverage: 42, socialImpact: 66, officialGap: 41 },
    trend: [3, 5, 4, 7, 8, 9, 9],
  }),
  mkTopic({
    id: "industry-noise-aksay",
    rank: null,
    title: "Обсуждение промышленного шума в пригороде",
    summary:
      "Часть жителей фиксирует повышенный уровень шума в вечернее время вблизи промзоны.",
    sector: "Экономика/промышленность",
    municipality: "Аксайский район",
    priority: "Наблюдение",
    score: 56,
    whyTop: "Территориальная концентрация сигналов и признаки дублирования части публикаций.",
    sourceCount: 4,
    officialSignal: false,
    contradiction: false,
    spamRisk: true,
    factors: { intensity: 45, coverage: 39, socialImpact: 62, officialGap: 38 },
    trend: [2, 3, 6, 5, 7, 9, 10],
  }),
];

const ROSTOV_TOPICS = [...TOP_PROBLEMS_ROSTOV, ...EXTRA_TOPICS_ROSTOV];

const ROSTOV_MUNICIPALITIES = [
  { name: "Ростов-на-Дону", signals: 58, critical: 3, topTopic: "Пробки и ремонт дорог", level: 0.92 },
  { name: "Батайск", signals: 47, critical: 2, topTopic: "Перебои с водоснабжением", level: 0.88 },
  { name: "Таганрог", signals: 36, critical: 1, topTopic: "Очереди в поликлиниках", level: 0.74 },
  { name: "Шахты", signals: 31, critical: 1, topTopic: "Перебои с электричеством", level: 0.71 },
  { name: "Аксайский район", signals: 29, critical: 1, topTopic: "Вывоз ТКО", level: 0.69 },
  { name: "Азов", signals: 24, critical: 1, topTopic: "Запах гари и задымление", level: 0.63 },
  { name: "Волгодонск", signals: 22, critical: 0, topTopic: "Проблемы УК/ТСЖ", level: 0.58 },
  { name: "Каменск-Шахтинский", signals: 20, critical: 1, topTopic: "Авария на теплосетях", level: 0.56 },
  { name: "Новочеркасск", signals: 18, critical: 0, topTopic: "Общественный транспорт", level: 0.51 },
  { name: "Сальский район", signals: 16, critical: 0, topTopic: "Состояние дорог", level: 0.47 },
  { name: "Красный Сулин", signals: 14, critical: 0, topTopic: "Качество воды", level: 0.43 },
  { name: "Семикаракорский район", signals: 12, critical: 0, topTopic: "Школьные маршруты", level: 0.4 },
];

const ROSTOV_SOURCES = [
  { id: "source-1", name: "DonDay Ростов", type: "СМИ", status: "СМИ", share: 12, topicCount: 34, reliability: 0.88, lastSeen: "04.04 11:20" },
  { id: "source-2", name: "161.ru", type: "СМИ", status: "СМИ", share: 9, topicCount: 28, reliability: 0.86, lastSeen: "04.04 10:55" },
  { id: "source-3", name: "Telegram: Ростов транспорт", type: "Telegram", status: "Пользовательский", share: 8, topicCount: 22, reliability: 0.63, lastSeen: "04.04 10:42" },
  { id: "source-4", name: "Telegram: Батайск городской", type: "Telegram", status: "Пользовательский", share: 7, topicCount: 20, reliability: 0.61, lastSeen: "04.04 10:02" },
  { id: "source-5", name: "VK: Аксай и район", type: "ВКонтакте", status: "Пользовательский", share: 7, topicCount: 19, reliability: 0.6, lastSeen: "04.04 09:58" },
  { id: "source-6", name: "VK: Таганрог городской диалог", type: "ВКонтакте", status: "Пользовательский", share: 6, topicCount: 17, reliability: 0.59, lastSeen: "04.04 09:10" },
  { id: "source-7", name: "Администрация Батайска", type: "Официальный", status: "Официальный", share: 6, topicCount: 14, reliability: 0.95, lastSeen: "04.04 08:34" },
  { id: "source-8", name: "Минздрав Ростовской области", type: "Официальный", status: "Официальный", share: 5, topicCount: 12, reliability: 0.96, lastSeen: "03.04 19:05" },
  { id: "source-9", name: "Минприроды Ростовской области", type: "Официальный", status: "Официальный", share: 4, topicCount: 9, reliability: 0.94, lastSeen: "04.04 08:22" },
  { id: "source-10", name: "RostovGazeta", type: "СМИ", status: "СМИ", share: 4, topicCount: 11, reliability: 0.82, lastSeen: "03.04 20:26" },
  { id: "source-11", name: "Открытые обращения граждан", type: "Публичные обращения", status: "Пользовательский", share: 11, topicCount: 30, reliability: 0.77, lastSeen: "04.04 11:05" },
];

const ROSTOV_TRENDS = {
  "24h": {
    label: "24 часа",
    timelineLabels: ["00:00", "04:00", "08:00", "12:00", "16:00", "20:00", "24:00"],
    volumeSeries: [42, 37, 58, 73, 69, 75, 64],
    spikes: [
      { time: "08:40", title: "Перебои с водоснабжением в Батайске", growth: "+34%" },
      { time: "10:15", title: "Пробки и ремонт дорог в Ростове-на-Дону", growth: "+27%" },
      { time: "18:20", title: "Жалобы на вывоз ТКО в Аксайском районе", growth: "+22%" },
    ],
    sectorDynamics: [
      { sector: "ЖКХ", change: 31, volume: 96 },
      { sector: "Транспорт", change: 22, volume: 71 },
      { sector: "Здравоохранение", change: 14, volume: 49 },
      { sector: "Экология/ЧС", change: 12, volume: 36 },
      { sector: "Благоустройство", change: 9, volume: 28 },
    ],
    geographyGrowth: [
      { municipality: "Батайск", growth: 34 },
      { municipality: "Ростов-на-Дону", growth: 27 },
      { municipality: "Таганрог", growth: 19 },
      { municipality: "Шахты", growth: 16 },
    ],
    complaintGrowth: 24,
  },
  "7d": {
    label: "7 дней",
    timelineLabels: ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"],
    volumeSeries: [210, 228, 244, 261, 279, 301, 318],
    spikes: [
      { time: "02.04", title: "Перебои с электричеством в Шахтах", growth: "+41%" },
      { time: "03.04", title: "Очереди в поликлинике в Таганроге", growth: "+33%" },
      { time: "04.04", title: "Перебои с водоснабжением в Батайске", growth: "+38%" },
    ],
    sectorDynamics: [
      { sector: "ЖКХ", change: 36, volume: 402 },
      { sector: "Транспорт", change: 24, volume: 311 },
      { sector: "Здравоохранение", change: 17, volume: 198 },
      { sector: "Экология/ЧС", change: 13, volume: 122 },
      { sector: "Благоустройство", change: 11, volume: 106 },
    ],
    geographyGrowth: [
      { municipality: "Батайск", growth: 38 },
      { municipality: "Аксайский район", growth: 29 },
      { municipality: "Ростов-на-Дону", growth: 26 },
      { municipality: "Шахты", growth: 21 },
    ],
    complaintGrowth: 31,
  },
  "30d": {
    label: "30 дней",
    timelineLabels: ["Нед 1", "Нед 2", "Нед 3", "Нед 4"],
    volumeSeries: [820, 912, 1048, 1213],
    spikes: [
      { time: "Нед 2", title: "Пробки и ремонт дорог в Ростове-на-Дону", growth: "+25%" },
      { time: "Нед 3", title: "Жалобы на вывоз ТКО в Аксайском районе", growth: "+31%" },
      { time: "Нед 4", title: "Перебои с водоснабжением в Батайске", growth: "+43%" },
    ],
    sectorDynamics: [
      { sector: "ЖКХ", change: 42, volume: 1460 },
      { sector: "Транспорт", change: 28, volume: 1092 },
      { sector: "Здравоохранение", change: 19, volume: 688 },
      { sector: "Экология/ЧС", change: 14, volume: 402 },
      { sector: "Благоустройство", change: 12, volume: 358 },
    ],
    geographyGrowth: [
      { municipality: "Батайск", growth: 41 },
      { municipality: "Ростов-на-Дону", growth: 36 },
      { municipality: "Таганрог", growth: 29 },
      { municipality: "Аксайский район", growth: 27 },
    ],
    complaintGrowth: 37,
  },
};

const ROSTOV_PROFILE = {
  fullName: "Ирина Кузнецова",
  position: "Аналитик ситуационного центра",
  role: "Региональный аналитик",
  department: "Правительство Ростовской области",
  email: "i.kuznetsova@donregion.ru",
};

export const DEFAULT_SETTINGS = {
  theme: "light",
  language: "ru",
  refreshRate: "15 минут",
  prioritySectors: ["ЖКХ", "Транспорт", "Здравоохранение"],
  publicOnly: true,
  integrations: {
    federalAppeals: false,
    system112: false,
    incidentsCenter: false,
  },
};

export const DEFAULT_NOTIFICATIONS = {
  critical: true,
  dailyDigest: true,
  weeklyDigest: false,
  anomalyAlerts: true,
};

const ROSTOV_REGION_DATA = {
  meta: {
    regionName: "Ростовская область",
    pilot: true,
    dataReady: true,
    lastUpdate: "4 апреля 2026, 11:20",
  },
  kpi: {
    totalTopics: 146,
    newCriticalTopics: 9,
    municipalitiesWithSignals: 37,
    officialConfirmedShare: 42,
  },
  overviewSummary: {
    day:
      "За последние 24 часа в регионе выделено 24 значимых темы. Наибольшая концентрация сигналов наблюдается в блоках ЖКХ и транспорта.",
    week:
      "За 7 дней выявлено 146 тем с общественно значимыми сигналами. Основной рост фиксируется по проблемам водоснабжения и обращения с ТКО.",
  },
  miniTrendLabels: ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"],
  miniTrendSeries: [52, 57, 64, 72, 78, 83, 88],
  criticalSignals: [
    {
      id: "critical-1",
      time: "11:02",
      title: "Рост сообщений о перебоях водоснабжения",
      municipality: "Батайск",
      source: "Telegram + обращения граждан",
      priority: "Критический",
    },
    {
      id: "critical-2",
      time: "10:45",
      title: "Нерегулярный вывоз ТКО на 3 площадках",
      municipality: "Аксайский район",
      source: "ВКонтакте + локальные каналы",
      priority: "Высокий",
    },
    {
      id: "critical-3",
      time: "10:15",
      title: "Пиковая нагрузка на дорожные участки ремонта",
      municipality: "Ростов-на-Дону",
      source: "СМИ + Telegram",
      priority: "Высокий",
    },
    {
      id: "critical-4",
      time: "09:50",
      title: "Очереди в поликлинике в утренний период",
      municipality: "Таганрог",
      source: "ВКонтакте + Telegram",
      priority: "Высокий",
    },
  ],
  topProblems: TOP_PROBLEMS_ROSTOV,
  topics: ROSTOV_TOPICS,
  municipalities: ROSTOV_MUNICIPALITIES,
  trends: ROSTOV_TRENDS,
  sources: ROSTOV_SOURCES,
  profile: ROSTOV_PROFILE,
  reportPreview:
    "Сводка фиксирует преобладание коммунальных и транспортных проблем с наибольшей интенсивностью в Батайске, Ростове-на-Дону и Аксайском районе.",
};

const EMPTY_REGION_DATA = (regionName) => ({
  meta: {
    regionName,
    pilot: false,
    dataReady: false,
    lastUpdate: "Данные подключаются",
  },
  kpi: {
    totalTopics: 0,
    newCriticalTopics: 0,
    municipalitiesWithSignals: 0,
    officialConfirmedShare: 0,
  },
  overviewSummary: {
    day: `Для региона «${regionName}» подключение источников в процессе.`,
    week: "После настройки источников появится недельная аналитическая сводка.",
  },
  miniTrendLabels: ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"],
  miniTrendSeries: [0, 0, 0, 0, 0, 0, 0],
  criticalSignals: [],
  topProblems: [],
  topics: [],
  municipalities: [],
  trends: {
    "24h": { label: "24 часа", timelineLabels: ["00:00", "04:00", "08:00", "12:00", "16:00", "20:00", "24:00"], volumeSeries: [0, 0, 0, 0, 0, 0, 0], spikes: [], sectorDynamics: [], geographyGrowth: [], complaintGrowth: 0 },
    "7d": { label: "7 дней", timelineLabels: ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"], volumeSeries: [0, 0, 0, 0, 0, 0, 0], spikes: [], sectorDynamics: [], geographyGrowth: [], complaintGrowth: 0 },
    "30d": { label: "30 дней", timelineLabels: ["Нед 1", "Нед 2", "Нед 3", "Нед 4"], volumeSeries: [0, 0, 0, 0], spikes: [], sectorDynamics: [], geographyGrowth: [], complaintGrowth: 0 },
  },
  sources: [],
  profile: ROSTOV_PROFILE,
  reportPreview: "Предпросмотр отчёта будет доступен после подключения первичных источников данных.",
});

const REGION_DATASETS = {
  "Ростовская область": ROSTOV_REGION_DATA,
  "Краснодарский край": EMPTY_REGION_DATA("Краснодарский край"),
  "Республика Татарстан": EMPTY_REGION_DATA("Республика Татарстан"),
  "Московская область": EMPTY_REGION_DATA("Московская область"),
  "Ленинградская область": EMPTY_REGION_DATA("Ленинградская область"),
  "Санкт-Петербург": EMPTY_REGION_DATA("Санкт-Петербург"),
  "Свердловская область": EMPTY_REGION_DATA("Свердловская область"),
  "Новосибирская область": EMPTY_REGION_DATA("Новосибирская область"),
  "Приморский край": EMPTY_REGION_DATA("Приморский край"),
};

export const getRegionData = (regionName) =>
  REGION_DATASETS[regionName] ?? EMPTY_REGION_DATA(regionName);

export const getAllSectors = (topics = []) =>
  Array.from(new Set(topics.map((topic) => topic.sector))).filter(Boolean);

export const getAllMunicipalities = (topics = []) =>
  Array.from(new Set(topics.map((topic) => topic.municipality))).filter(Boolean);

export const SOURCE_TYPE_OPTIONS = ["Все", "СМИ", "Telegram", "ВКонтакте", "Официальный", "Публичные обращения"];
export const SOURCE_STATUS_OPTIONS = ["Все", "Официальный", "Пользовательский", "СМИ"];
export const PERIOD_OPTIONS = [
  { value: "24h", label: "24 часа" },
  { value: "7d", label: "7 дней" },
  { value: "30d", label: "30 дней" },
];

