import { useEffect, useMemo, useRef, useState } from "react";
import Badge, { getPriorityTone } from "../components/common/Badge";
import {
  ROSTOV_MUNICIPALITY_GEOMETRIES,
  ROSTOV_REGION_GEOMETRY,
} from "../data/rostovGeoData";

const VIEWBOX = { width: 780, height: 560, padding: 34 };
const DEFAULT_MUNICIPALITY = "\u0420\u043e\u0441\u0442\u043e\u0432-\u043d\u0430-\u0414\u043e\u043d\u0443";
const DEFAULT_FOCUS = { x: VIEWBOX.width / 2, y: VIEWBOX.height / 2 };
const MAP_DRAG_THRESHOLD = 5;
const MAP_DRAG_SENSITIVITY = 0.92;

const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
const clamp01 = (value) => clamp(value, 0, 1);

const getZoneHeatColor = (heat) => {
  const normalized = clamp01(heat);
  const hue = 214 - normalized * 206;
  const saturation = 64;
  const lightness = 89 - normalized * 28;
  return `hsl(${hue.toFixed(1)} ${saturation}% ${lightness.toFixed(1)}%)`;
};

const getTransform = (focus, zoom, width, height) => {
  const centerX = width / 2;
  const centerY = height / 2;
  return `translate(${centerX} ${centerY}) scale(${zoom}) translate(${-focus.x} ${-focus.y})`;
};

const isPoint = (value) =>
  Array.isArray(value) &&
  value.length >= 2 &&
  Number.isFinite(value[0]) &&
  Number.isFinite(value[1]);

const collectRings = (node, rings = []) => {
  if (!Array.isArray(node)) {
    return rings;
  }
  if (node.length > 2 && node.every(isPoint)) {
    rings.push(node);
    return rings;
  }
  node.forEach((child) => collectRings(child, rings));
  return rings;
};

const getOuterRings = (geometry) => {
  if (!geometry?.coordinates) {
    return [];
  }

  if (geometry.type === "Polygon") {
    return Array.isArray(geometry.coordinates?.[0]) ? [geometry.coordinates[0]] : [];
  }

  if (geometry.type === "MultiPolygon") {
    return geometry.coordinates
      .map((polygon) => (Array.isArray(polygon?.[0]) ? polygon[0] : null))
      .filter(Boolean);
  }

  return collectRings(geometry.coordinates);
};

const ROSTOV_URBAN_DISTRICT_NAMES = new Set([
  "\u0412\u043e\u0440\u043e\u0448\u0438\u043b\u043e\u0432\u0441\u043a\u0438\u0439 \u0440\u0430\u0439\u043e\u043d",
  "\u0416\u0435\u043b\u0435\u0437\u043d\u043e\u0434\u043e\u0440\u043e\u0436\u043d\u044b\u0439 \u0440\u0430\u0439\u043e\u043d",
  "\u041a\u0438\u0440\u043e\u0432\u0441\u043a\u0438\u0439 \u0440\u0430\u0439\u043e\u043d",
  "\u041b\u0435\u043d\u0438\u043d\u0441\u043a\u0438\u0439 \u0440\u0430\u0439\u043e\u043d",
  "\u041e\u043a\u0442\u044f\u0431\u0440\u044c\u0441\u043a\u0438\u0439 \u0440\u0430\u0439\u043e\u043d",
  "\u041f\u0435\u0440\u0432\u043e\u043c\u0430\u0439\u0441\u043a\u0438\u0439 \u0440\u0430\u0439\u043e\u043d",
  "\u041f\u0440\u043e\u043b\u0435\u0442\u0430\u0440\u0441\u043a\u0438\u0439 \u0440\u0430\u0439\u043e\u043d",
  "\u0421\u043e\u0432\u0435\u0442\u0441\u043a\u0438\u0439 \u0440\u0430\u0439\u043e\u043d",
]);

const pointInRing = (point, ring) => {
  if (!Array.isArray(point) || !Array.isArray(ring) || ring.length < 3) {
    return false;
  }

  let inside = false;
  const [px, py] = point;

  for (let index = 0, previous = ring.length - 1; index < ring.length; previous = index, index += 1) {
    const [x1, y1] = ring[index];
    const [x2, y2] = ring[previous];
    const intersects = y1 > py !== y2 > py && px < ((x2 - x1) * (py - y1)) / (y2 - y1 + Number.EPSILON) + x1;
    if (intersects) {
      inside = !inside;
    }
  }

  return inside;
};

const pointInGeometry = (point, geometry) => getOuterRings(geometry).some((ring) => pointInRing(point, ring));

const estimateRingArea = (ring) => {
  if (!Array.isArray(ring) || ring.length < 3) {
    return 0;
  }

  let area = 0;
  for (let index = 0; index < ring.length; index += 1) {
    const [x1, y1] = ring[index];
    const [x2, y2] = ring[(index + 1) % ring.length];
    area += x1 * y2 - x2 * y1;
  }
  return Math.abs(area / 2);
};

const estimateGeometryArea = (geometry) => {
  if (!geometry?.coordinates) {
    return 0;
  }
  return collectRings(geometry.coordinates).reduce((sum, ring) => sum + estimateRingArea(ring), 0);
};

const toLabelName = (name = "") =>
  name
    .replace(/\s+\u0440\u0430\u0439\u043e\u043d$/i, "")
    .replace(/^\u0433\u043e\u0440\u043e\u0434\s+/i, "")
    .trim();

const getGeometryPoints = (geometry) => {
  return getOuterRings(geometry).flat();
};

const getBounds = (geometries) => {
  let minLon = Number.POSITIVE_INFINITY;
  let maxLon = Number.NEGATIVE_INFINITY;
  let minLat = Number.POSITIVE_INFINITY;
  let maxLat = Number.NEGATIVE_INFINITY;

  geometries.forEach((geometry) => {
    getGeometryPoints(geometry).forEach(([lon, lat]) => {
      if (lon < minLon) {
        minLon = lon;
      }
      if (lon > maxLon) {
        maxLon = lon;
      }
      if (lat < minLat) {
        minLat = lat;
      }
      if (lat > maxLat) {
        maxLat = lat;
      }
    });
  });

  if (!Number.isFinite(minLon) || !Number.isFinite(minLat)) {
    return {
      minLon: 39.0,
      maxLon: 41.2,
      minLat: 46.2,
      maxLat: 48.2,
    };
  }

  return { minLon, maxLon, minLat, maxLat };
};

const createProjector = (bounds, width, height, padding) => {
  const dataWidth = Math.max(bounds.maxLon - bounds.minLon, 0.0001);
  const dataHeight = Math.max(bounds.maxLat - bounds.minLat, 0.0001);
  const scale = Math.min((width - padding * 2) / dataWidth, (height - padding * 2) / dataHeight);
  const offsetX = (width - dataWidth * scale) / 2;
  const offsetY = (height - dataHeight * scale) / 2;

  return ([lon, lat]) => {
    const x = (lon - bounds.minLon) * scale + offsetX;
    const y = (bounds.maxLat - lat) * scale + offsetY;
    return [x, y];
  };
};

const geometryToPath = (geometry, projectPoint) => {
  if (!geometry?.coordinates) {
    return "";
  }

  const rings = getOuterRings(geometry);
  return rings
    .map((ring) => {
      const body = ring
        .map(([lon, lat], index) => {
          const [x, y] = projectPoint([lon, lat]);
          return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
        })
        .join(" ");
      return `${body} Z`;
    })
    .join(" ");
};

const ROSTOV_CITY_GEOMETRY =
  ROSTOV_MUNICIPALITY_GEOMETRIES.find(
    (item) => item.name === "\u0420\u043e\u0441\u0442\u043e\u0432-\u043d\u0430-\u0414\u043e\u043d\u0443",
  )?.geometry ?? null;

const CITY_ZONE_BASE = ROSTOV_MUNICIPALITY_GEOMETRIES.filter((item) => {
  if (!ROSTOV_CITY_GEOMETRY) {
    return true;
  }

  // Hide inner city districts so Rostov appears as one single zone.
  const nestedRostovDistrict =
    ROSTOV_URBAN_DISTRICT_NAMES.has(item.name) && pointInGeometry(item.center, ROSTOV_CITY_GEOMETRY);
  return !nestedRostovDistrict;
}).map((item) => ({
  ...item,
  displayName: item.name,
  sourceName: item.name,
  short: item.short ?? item.name,
  labelName: toLabelName(item.short ?? item.name),
}));

const GEO_PROBLEM_AREA_DETAILS = {
  "water-bataysk": [
    {
      id: "water-bataysk-aviagorodok",
      area: "\u0410\u0432\u0438\u0430\u0433\u043e\u0440\u043e\u0434\u043e\u043a",
      issue:
        "\u0421\u043d\u0438\u0436\u0435\u043d\u0438\u0435 \u0434\u0430\u0432\u043b\u0435\u043d\u0438\u044f \u0438 \u043b\u043e\u043a\u0430\u043b\u044c\u043d\u044b\u0435 \u043e\u0442\u043a\u043b\u044e\u0447\u0435\u043d\u0438\u044f \u0432\u043e\u0434\u044b \u0432 \u0432\u0435\u0447\u0435\u0440\u043d\u0438\u0435 \u0447\u0430\u0441\u044b.",
      sector: "\u0416\u041a\u0425",
      priority: "\u041a\u0440\u0438\u0442\u0438\u0447\u0435\u0441\u043a\u0438\u0439",
      signals: 24,
      status: "\u0422\u0440\u0435\u0431\u0443\u0435\u0442\u0441\u044f \u0440\u0435\u0430\u0433\u0438\u0440\u043e\u0432\u0430\u043d\u0438\u0435",
    },
    {
      id: "water-bataysk-severny",
      area: "\u0421\u0435\u0432\u0435\u0440\u043d\u044b\u0439 \u043c\u0438\u043a\u0440\u043e\u0440\u0430\u0439\u043e\u043d",
      issue:
        "\u0424\u0438\u043a\u0441\u0438\u0440\u0443\u044e\u0442\u0441\u044f \u043f\u0435\u0440\u0435\u0431\u043e\u0438 \u0432 \u0433\u0440\u0430\u0444\u0438\u043a\u0435 \u043f\u043e\u0434\u0430\u0447\u0438 \u0432\u043e\u0434\u044b \u0438 \u043f\u043e\u0432\u0442\u043e\u0440\u043d\u044b\u0435 \u043e\u0431\u0440\u0430\u0449\u0435\u043d\u0438\u044f.",
      sector: "\u0416\u041a\u0425",
      priority: "\u0412\u044b\u0441\u043e\u043a\u0438\u0439",
      signals: 18,
      status: "\u0412 \u043c\u043e\u043d\u0438\u0442\u043e\u0440\u0438\u043d\u0433\u0435",
    },
    {
      id: "water-bataysk-vostochny",
      area: "\u0412\u043e\u0441\u0442\u043e\u0447\u043d\u044b\u0439 \u0441\u0435\u043a\u0442\u043e\u0440",
      issue:
        "\u041f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043d\u044b \u0441\u0438\u0433\u043d\u0430\u043b\u044b \u043e \u043d\u0435\u0440\u0430\u0432\u043d\u043e\u043c\u0435\u0440\u043d\u043e\u0439 \u043f\u043e\u0434\u0430\u0447\u0435 \u0432\u043e\u0434\u043e\u0441\u043d\u0430\u0431\u0436\u0435\u043d\u0438\u044f.",
      sector: "\u0416\u041a\u0425",
      priority: "\u0412\u044b\u0441\u043e\u043a\u0438\u0439",
      signals: 15,
      status: "\u0423\u0442\u043e\u0447\u043d\u044f\u0435\u0442\u0441\u044f",
    },
  ],
  "roads-rostov": [
    {
      id: "roads-rostov-vorosh",
      area: "\u0412\u043e\u0440\u043e\u0448\u0438\u043b\u043e\u0432\u0441\u043a\u0438\u0439 \u0440\u0430\u0439\u043e\u043d",
      issue:
        "\u041f\u0438\u043a\u043e\u0432\u0430\u044f \u0437\u0430\u0433\u0440\u0443\u0436\u0435\u043d\u043d\u043e\u0441\u0442\u044c \u043f\u043e \u043e\u0441\u043d\u043e\u0432\u043d\u044b\u043c \u0443\u0447\u0430\u0441\u0442\u043a\u0430\u043c \u0434\u043e\u0440\u043e\u0436\u043d\u043e\u0433\u043e \u0440\u0435\u043c\u043e\u043d\u0442\u0430.",
      sector: "\u0422\u0440\u0430\u043d\u0441\u043f\u043e\u0440\u0442",
      priority: "\u0412\u044b\u0441\u043e\u043a\u0438\u0439",
      signals: 19,
      status: "\u0422\u0440\u0435\u0431\u0443\u0435\u0442\u0441\u044f \u043a\u043e\u043e\u0440\u0434\u0438\u043d\u0430\u0446\u0438\u044f \u0441\u0445\u0435\u043c",
    },
    {
      id: "roads-rostov-zapadny",
      area: "\u0417\u0430\u043f\u0430\u0434\u043d\u044b\u0439 \u0436\u0438\u043b\u043e\u0439 \u043c\u0430\u0441\u0441\u0438\u0432",
      issue:
        "\u0420\u043e\u0441\u0442 \u0432\u0440\u0435\u043c\u0435\u043d\u0438 \u043f\u0440\u043e\u0435\u0437\u0434\u0430 \u043d\u0430 \u043c\u0430\u0440\u0448\u0440\u0443\u0442\u0430\u0445 \u043e\u0431\u044a\u0435\u0437\u0434\u0430 \u0438 \u043f\u043e\u0432\u0442\u043e\u0440\u043d\u044b\u0435 \u0436\u0430\u043b\u043e\u0431\u044b.",
      sector: "\u0422\u0440\u0430\u043d\u0441\u043f\u043e\u0440\u0442",
      priority: "\u0412\u044b\u0441\u043e\u043a\u0438\u0439",
      signals: 14,
      status: "\u0412 \u043c\u043e\u043d\u0438\u0442\u043e\u0440\u0438\u043d\u0433\u0435",
    },
    {
      id: "roads-rostov-center",
      area: "\u0426\u0435\u043d\u0442\u0440\u0430\u043b\u044c\u043d\u0430\u044f \u0447\u0430\u0441\u0442\u044c",
      issue:
        "\u041e\u0442\u043c\u0435\u0447\u0430\u044e\u0442\u0441\u044f \u043d\u0430\u0433\u0440\u0443\u0437\u043a\u0438 \u043d\u0430 \u043f\u0435\u0440\u0435\u0441\u0430\u0434\u043e\u0447\u043d\u044b\u0445 \u0443\u0437\u043b\u0430\u0445 \u0438 \u043f\u043e\u0434\u0445\u043e\u0434\u0430\u0445 \u043a \u043c\u043e\u0441\u0442\u0430\u043c.",
      sector: "\u0422\u0440\u0430\u043d\u0441\u043f\u043e\u0440\u0442",
      priority: "\u0421\u0440\u0435\u0434\u043d\u0438\u0439",
      signals: 12,
      status: "\u0410\u043d\u0430\u043b\u0438\u0442\u0438\u043a\u0430 \u0430\u043a\u0442\u0443\u0430\u043b\u0438\u0437\u0438\u0440\u0443\u0435\u0442\u0441\u044f",
    },
  ],
  "clinic-taganrog": [
    {
      id: "clinic-taganrog-center",
      area: "\u0426\u0435\u043d\u0442\u0440 \u0422\u0430\u0433\u0430\u043d\u0440\u043e\u0433\u0430",
      issue:
        "\u0423\u0432\u0435\u043b\u0438\u0447\u0438\u0432\u0430\u0435\u0442\u0441\u044f \u0432\u0440\u0435\u043c\u044f \u043e\u0436\u0438\u0434\u0430\u043d\u0438\u044f \u043f\u0435\u0440\u0432\u0438\u0447\u043d\u043e\u0433\u043e \u043f\u0440\u0438\u0451\u043c\u0430 \u0432 \u0443\u0442\u0440\u0435\u043d\u043d\u0438\u0435 \u0447\u0430\u0441\u044b.",
      sector: "\u0417\u0434\u0440\u0430\u0432\u043e\u043e\u0445\u0440\u0430\u043d\u0435\u043d\u0438\u0435",
      priority: "\u0412\u044b\u0441\u043e\u043a\u0438\u0439",
      signals: 10,
      status: "\u0412 \u0440\u0430\u0431\u043e\u0442\u0435",
    },
    {
      id: "clinic-taganrog-vostok",
      area: "\u0412\u043e\u0441\u0442\u043e\u0447\u043d\u044b\u0439 \u0441\u0435\u043a\u0442\u043e\u0440",
      issue:
        "\u0424\u0438\u043a\u0441\u0438\u0440\u0443\u044e\u0442\u0441\u044f \u043f\u0435\u0440\u0435\u043d\u043e\u0441\u044b \u043f\u043b\u0430\u043d\u043e\u0432\u044b\u0445 \u043f\u0440\u0438\u0451\u043c\u043e\u0432 \u0438 \u0437\u0430\u043f\u0440\u043e\u0441\u044b \u043d\u0430 \u0434\u043e\u043f\u043e\u043b\u043d\u0438\u0442\u0435\u043b\u044c\u043d\u044b\u0435 \u0442\u0430\u043b\u043e\u043d\u044b.",
      sector: "\u0417\u0434\u0440\u0430\u0432\u043e\u043e\u0445\u0440\u0430\u043d\u0435\u043d\u0438\u0435",
      priority: "\u0421\u0440\u0435\u0434\u043d\u0438\u0439",
      signals: 7,
      status: "\u041f\u043e\u0434 \u043a\u043e\u043d\u0442\u0440\u043e\u043b\u0435\u043c",
    },
  ],
  "electricity-shakhty": [
    {
      id: "electricity-shakhty-artem",
      area: "\u043c\u043a\u0440. \u0410\u0440\u0442\u0451\u043c",
      issue:
        "\u041a\u0440\u0430\u0442\u043a\u043e\u0432\u0440\u0435\u043c\u0435\u043d\u043d\u044b\u0435 \u043e\u0442\u043a\u043b\u044e\u0447\u0435\u043d\u0438\u044f \u044d\u043b\u0435\u043a\u0442\u0440\u043e\u0441\u043d\u0430\u0431\u0436\u0435\u043d\u0438\u044f \u0432 \u0432\u0435\u0447\u0435\u0440\u043d\u0438\u0435 \u0447\u0430\u0441\u044b.",
      sector: "\u0416\u041a\u0425",
      priority: "\u0412\u044b\u0441\u043e\u043a\u0438\u0439",
      signals: 9,
      status: "\u041d\u0443\u0436\u043d\u0430 \u043f\u0440\u043e\u0432\u0435\u0440\u043a\u0430 \u0441\u0435\u0442\u0435\u0439",
    },
    {
      id: "electricity-shakhty-center",
      area: "\u0426\u0435\u043d\u0442\u0440\u0430\u043b\u044c\u043d\u0430\u044f \u0447\u0430\u0441\u0442\u044c",
      issue:
        "\u041f\u043e \u0441\u0435\u0442\u044f\u043c \u0441\u0440\u0435\u0434\u043d\u0435\u0433\u043e \u043d\u0430\u043f\u0440\u044f\u0436\u0435\u043d\u0438\u044f \u0444\u0438\u043a\u0441\u0438\u0440\u0443\u0435\u0442\u0441\u044f \u0440\u043e\u0441\u0442 \u043e\u0431\u0440\u0430\u0449\u0435\u043d\u0438\u0439 \u0432 \u0447\u0430\u0441\u044b \u043f\u0438\u043a\u0430.",
      sector: "\u0416\u041a\u0425",
      priority: "\u0421\u0440\u0435\u0434\u043d\u0438\u0439",
      signals: 6,
      status: "\u0412 \u043c\u043e\u043d\u0438\u0442\u043e\u0440\u0438\u043d\u0433\u0435",
    },
  ],
};

const getProblemAreaDetails = (problem) => {
  if (!problem) {
    return [];
  }

  const preset = GEO_PROBLEM_AREA_DETAILS[problem.id];
  if (preset?.length) {
    return preset;
  }

  const baseSignals = Math.max(6, Math.round((problem.sourceCount ?? 6) * 0.9));
  return [
    {
      id: `${problem.id}-center`,
      area: "Центральный сектор",
      issue: problem.summary,
      sector: problem.sector,
      priority: problem.priority,
      signals: Math.max(3, Math.round(baseSignals * 0.42)),
      status: "Требуется проверка",
    },
    {
      id: `${problem.id}-north`,
      area: "Северный сектор",
      issue: `Фиксируется локальная динамика: ${problem.summary.toLowerCase()}`,
      sector: problem.sector,
      priority: problem.priority,
      signals: Math.max(2, Math.round(baseSignals * 0.33)),
      status: "В мониторинге",
    },
    {
      id: `${problem.id}-south`,
      area: "Южный сектор",
      issue: "Нужна дополнительная верификация сигналов и уточнение масштаба проблемы.",
      sector: problem.sector,
      priority: problem.priority,
      signals: Math.max(2, Math.round(baseSignals * 0.25)),
      status: "Данные уточняются",
    },
  ];
};

const buildAreaTopic = (problem, area) => {
  const normalizedIssue = area.issue?.trim() || problem.summary;
  const normalizedArea = area.area?.trim() || "Локальный сектор";
  const normalizedStatus = area.status?.trim() || "Данные уточняются";
  const normalizedSignals = Number.isFinite(area.signals) ? area.signals : problem.sourceCount;
  const normalizedSector = area.sector || problem.sector;

  return {
    ...problem,
    id: `${problem.id}-${area.id}`,
    title: `${problem.title}: ${normalizedArea}`,
    summary: normalizedIssue,
    municipality: `${problem.municipality}, ${normalizedArea}`,
    sourceCount: normalizedSignals,
    score: Math.max(1, Math.min(99, Math.round(problem.score * 0.84 + normalizedSignals * 1.6))),
    whyTop: `Локальная концентрация сигналов в зоне «${normalizedArea}». Статус: ${normalizedStatus}.`,
    snippets: [
      `Локальная зона: ${normalizedArea}.`,
      normalizedIssue,
      `Статус мониторинга: ${normalizedStatus}.`,
    ],
    timeline: [
      ...(problem.timeline ?? []),
      {
        date: "Сейчас",
        event: `Выделен локальный контур: ${normalizedArea}.`,
      },
    ],
  };
};

const clampFocusByZoom = (focus, zoom) => {
  const halfWidth = VIEWBOX.width / (2 * zoom);
  const halfHeight = VIEWBOX.height / (2 * zoom);

  return {
    x: clamp(focus.x, halfWidth, VIEWBOX.width - halfWidth),
    y: clamp(focus.y, halfHeight, VIEWBOX.height - halfHeight),
  };
};

export default function GeographyPage({
  municipalities = [],
  topProblems = [],
  onOpenTopic,
}) {
  const svgRef = useRef(null);
  const dragStateRef = useRef({
    active: false,
    startX: 0,
    startY: 0,
    originX: DEFAULT_FOCUS.x,
    originY: DEFAULT_FOCUS.y,
  });
  const dragMovedRef = useRef(false);
  const suppressClickRef = useRef(false);
  const suppressClickTimerRef = useRef(null);
  const [selectedMunicipality, setSelectedMunicipality] = useState(DEFAULT_MUNICIPALITY);
  const [hoveredMunicipality, setHoveredMunicipality] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const [isAutoFocusEnabled, setIsAutoFocusEnabled] = useState(true);
  const [expandedProblemId, setExpandedProblemId] = useState("");
  const [zoomLevel, setZoomLevel] = useState(1.25);
  const [viewState, setViewState] = useState({ zoom: 1.25, x: DEFAULT_FOCUS.x, y: DEFAULT_FOCUS.y });

  const municipalityStatsByName = useMemo(
    () => Object.fromEntries(municipalities.map((item) => [item.name, item])),
    [municipalities],
  );

  useEffect(() => {
    if (!CITY_ZONE_BASE.length) {
      setSelectedMunicipality("");
      return;
    }
    setSelectedMunicipality((current) => {
      if (current && CITY_ZONE_BASE.some((item) => item.sourceName === current)) {
        return current;
      }
      return CITY_ZONE_BASE[0]?.sourceName ?? "";
    });
  }, []);

  const allCityMeta = useMemo(
    () =>
      CITY_ZONE_BASE.map((item) => {
        const metrics = municipalityStatsByName[item.sourceName];
        return {
          ...item,
          signals: metrics?.signals ?? 0,
          critical: metrics?.critical ?? 0,
          topTopic: metrics?.topTopic ?? "Данные в мониторинге",
          level: metrics?.level ?? 0.08,
        };
      }),
    [municipalityStatsByName],
  );

  const cityBySourceName = useMemo(
    () => Object.fromEntries(allCityMeta.map((item) => [item.sourceName, item])),
    [allCityMeta],
  );

  const regionBounds = useMemo(
    () => getBounds([ROSTOV_REGION_GEOMETRY, ...allCityMeta.map((item) => item.geometry)]),
    [allCityMeta],
  );
  const projectRegion = useMemo(
    () => createProjector(regionBounds, VIEWBOX.width, VIEWBOX.height, VIEWBOX.padding),
    [regionBounds],
  );

  const regionOutlinePath = useMemo(
    () => geometryToPath(ROSTOV_REGION_GEOMETRY, projectRegion),
    [projectRegion],
  );

  const regionZones = useMemo(
    () => {
      const maxSignals = allCityMeta.reduce(
        (max, zone) => (zone.signals > max ? zone.signals : max),
        0,
      );
      const heatDivider = Math.max(1, Math.log1p(maxSignals));

      return allCityMeta.map((zone) => {
        const hasNews = Number(zone.signals) > 0;
        const normalizedBySignals = hasNews
          ? Math.log1p(zone.signals) / heatDivider
          : 0;
        const heat = hasNews ? clamp01(0.14 + normalizedBySignals * 0.86) : 0;
        const [x, y] = projectRegion(zone.center);
        return {
          ...zone,
          d: geometryToPath(zone.geometry, projectRegion),
          x,
          y,
          area: estimateGeometryArea(zone.geometry),
          heat,
          fillColor: getZoneHeatColor(heat),
        };
      });
    },
    [allCityMeta, projectRegion],
  );

  const hoveredZone = useMemo(
    () => regionZones.find((zone) => zone.sourceName === hoveredMunicipality) ?? null,
    [hoveredMunicipality, regionZones],
  );

  const selectedZone = selectedMunicipality
    ? regionZones.find((zone) => zone.sourceName === selectedMunicipality) ?? null
    : null;

  const drawZones = useMemo(
    () => [...regionZones].sort((left, right) => right.area - left.area),
    [regionZones],
  );

  const orderedZones = useMemo(() => {
    const elevated = new Set([selectedMunicipality, hoveredMunicipality].filter(Boolean));
    const baseZones = drawZones.filter((zone) => !elevated.has(zone.sourceName));
    const elevatedZones = drawZones.filter((zone) => elevated.has(zone.sourceName));
    return [...baseZones, ...elevatedZones];
  }, [drawZones, hoveredMunicipality, selectedMunicipality]);

  const overlayLabelZone = hoveredZone ?? selectedZone;
  const selectedMunicipalityData = selectedZone
    ? cityBySourceName[selectedZone.sourceName]
    : null;

  const municipalProblems = useMemo(
    () => topProblems.filter((problem) => problem.municipality === selectedMunicipality),
    [selectedMunicipality, topProblems],
  );
  const municipalitiesWithNews = useMemo(
    () =>
      new Set(
        allCityMeta
          .filter((item) => Number(item.signals) > 0)
          .map((item) => item.sourceName),
      ),
    [allCityMeta],
  );
  const municipalProblemDetails = useMemo(
    () => Object.fromEntries(municipalProblems.map((problem) => [problem.id, getProblemAreaDetails(problem)])),
    [municipalProblems],
  );
  const selectedMunicipalityLead = municipalProblems[0] ?? null;

  useEffect(() => {
    setExpandedProblemId("");
  }, [selectedMunicipality]);

  useEffect(
    () => () => {
      if (suppressClickTimerRef.current) {
        window.clearTimeout(suppressClickTimerRef.current);
      }
    },
    [],
  );

  useEffect(() => {
    if (isDragging) {
      return undefined;
    }

    let frameId = null;

    const step = () => {
      let done = false;
      setViewState((current) => {
        const targetX = isAutoFocusEnabled && selectedZone ? selectedZone.x : current.x;
        const targetY = isAutoFocusEnabled && selectedZone ? selectedZone.y : current.y;
        const nextZoom = current.zoom + (zoomLevel - current.zoom) * 0.18;
        const nextX = current.x + (targetX - current.x) * 0.18;
        const nextY = current.y + (targetY - current.y) * 0.18;
        done =
          Math.abs(nextZoom - zoomLevel) < 0.004 &&
          Math.abs(nextX - targetX) < 0.4 &&
          Math.abs(nextY - targetY) < 0.4;

        if (done) {
          return { zoom: zoomLevel, x: targetX, y: targetY };
        }
        return { zoom: nextZoom, x: nextX, y: nextY };
      });

      if (!done) {
        frameId = window.requestAnimationFrame(step);
      }
    };

    frameId = window.requestAnimationFrame(step);
    return () => {
      if (frameId) {
        window.cancelAnimationFrame(frameId);
      }
    };
  }, [isAutoFocusEnabled, isDragging, zoomLevel, selectedZone?.x, selectedZone?.y]);

  const zoomIn = () => {
    setZoomLevel((current) => clamp(Number((current + 0.65).toFixed(2)), 1, 9));
  };

  const zoomOut = () => {
    setZoomLevel((current) => clamp(Number((current - 0.65).toFixed(2)), 1, 9));
  };

  const selectZone = (zoneSourceName) => {
    setSelectedMunicipality(zoneSourceName);
    setIsAutoFocusEnabled(true);
    setZoomLevel((current) => (current < 2.6 ? 2.6 : current));
  };

  const finishMapDrag = () => {
    if (!dragStateRef.current.active) {
      return;
    }

    if (dragMovedRef.current) {
      suppressClickRef.current = true;
      if (suppressClickTimerRef.current) {
        window.clearTimeout(suppressClickTimerRef.current);
      }
      suppressClickTimerRef.current = window.setTimeout(() => {
        suppressClickRef.current = false;
      }, 180);
    }

    dragStateRef.current.active = false;
    dragMovedRef.current = false;
    setIsDragging(false);
    setHoveredMunicipality("");
  };

  const handleMapMouseDown = (event) => {
    if (event.button !== 0) {
      return;
    }
    event.preventDefault();

    dragStateRef.current = {
      active: true,
      startX: event.clientX,
      startY: event.clientY,
      originX: viewState.x,
      originY: viewState.y,
    };
    setIsAutoFocusEnabled(false);
    dragMovedRef.current = false;
    setIsDragging(true);
  };

  const handleMapMouseMove = (event) => {
    if (!dragStateRef.current.active) {
      return;
    }
    event.preventDefault();

    const deltaX = event.clientX - dragStateRef.current.startX;
    const deltaY = event.clientY - dragStateRef.current.startY;

    if (!dragMovedRef.current && Math.hypot(deltaX, deltaY) >= MAP_DRAG_THRESHOLD) {
      dragMovedRef.current = true;
    }

    const nextFocus = clampFocusByZoom(
      {
        x: dragStateRef.current.originX - (deltaX / viewState.zoom) * MAP_DRAG_SENSITIVITY,
        y: dragStateRef.current.originY - (deltaY / viewState.zoom) * MAP_DRAG_SENSITIVITY,
      },
      viewState.zoom,
    );

    setViewState((current) => ({
      ...current,
      x: nextFocus.x,
      y: nextFocus.y,
    }));
  };

  const handleMapClickCapture = (event) => {
    if (!suppressClickRef.current) {
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    suppressClickRef.current = false;
  };

  const toggleProblemDistricts = (problemId) => {
    setExpandedProblemId((current) => (current === problemId ? "" : problemId));
  };

  const handleMapBackgroundClick = () => {
    setSelectedMunicipality("");
    setExpandedProblemId("");
    setHoveredMunicipality("");
    setIsAutoFocusEnabled(false);
  };

  const chipList = useMemo(
    () => [...allCityMeta].sort((a, b) => b.signals - a.signals),
    [allCityMeta],
  );

  const mapTransform = getTransform(
    { x: viewState.x, y: viewState.y },
    viewState.zoom,
    VIEWBOX.width,
    VIEWBOX.height,
  );

  return (
    <div className="page">
      <div className="overview-grid geography-grid">
        <section className="card animate-in geo-map-card geo-map-card-premium">
          <div className="section-head">
            <h2>Оперативная карта Ростовской области</h2>
            <span>Все муниципалитеты Ростовской области</span>
          </div>

          <div className="geo-map-toolbar">
            {hoveredZone && <span className="geo-hover-chip">На карте: {hoveredZone.labelName}</span>}
            <div className="geo-zoom-controls">
              <button
                type="button"
                className="ghost-button"
                onClick={zoomOut}
                aria-label="Уменьшить карту"
              >
                −
              </button>
              <span>{Math.round(viewState.zoom * 100)}%</span>
              <button
                type="button"
                className="ghost-button"
                onClick={zoomIn}
                aria-label="Увеличить карту"
              >
                +
              </button>
            </div>
            <div className="geo-heat-legend" aria-hidden="true">
              <small>Меньше новостей</small>
              <span className="geo-heat-bar" />
              <small>Больше новостей</small>
            </div>
          </div>

          <div className="geo-focus-banner">
            <div className="geo-focus-head">
              <h3>{selectedMunicipalityData?.labelName ?? "Территория не выбрана"}</h3>
              {selectedMunicipalityLead && (
                <Badge
                  text={selectedMunicipalityLead.priority}
                  tone={getPriorityTone(selectedMunicipalityLead.priority)}
                />
              )}
            </div>
            <p>
              {selectedMunicipalityLead?.summary ??
                `Основная тема: ${selectedMunicipalityData?.topTopic ?? "данные уточняются"}.`}
            </p>
            <div className="geo-focus-meta">
              <span>Сигналов: {selectedMunicipalityData?.signals ?? 0}</span>
              <span>Критических тем: {selectedMunicipalityData?.critical ?? 0}</span>
              <span>Проблем в приоритете: {municipalProblems.length}</span>
            </div>
          </div>

          <div className={`geo-map-stage geo-map-stage-premium ${isDragging ? "dragging" : ""}`}>
            <svg
              ref={svgRef}
              className={`geo-map geo-map-region ${isDragging ? "is-dragging" : ""}`}
              viewBox={`0 0 ${VIEWBOX.width} ${VIEWBOX.height}`}
              role="img"
              aria-label="Карта муниципалитетов Ростовской области"
              onMouseDown={handleMapMouseDown}
              onMouseMove={handleMapMouseMove}
              onMouseUp={finishMapDrag}
              onMouseLeave={finishMapDrag}
              onClickCapture={handleMapClickCapture}
              onClick={handleMapBackgroundClick}
              onDragStart={(event) => event.preventDefault()}
            >
              <g transform={mapTransform}>
                <path d={regionOutlinePath} className="geo-region-outline" />
                {orderedZones.map((zone) => {
                  const isActive = selectedMunicipality === zone.sourceName;
                  const isHovered = hoveredMunicipality === zone.sourceName;
                  const hasNews = municipalitiesWithNews.has(zone.sourceName);
                  return (
                    <g
                      key={zone.sourceName}
                      className={`map-zone-wrap ${isActive ? "active" : ""} ${isHovered ? "hovered" : ""} ${hasNews ? "" : "no-data"}`}
                      onMouseEnter={() => {
                        if (!isDragging && hasNews) {
                          setHoveredMunicipality(zone.sourceName);
                        }
                      }}
                      onMouseLeave={() => {
                        if (!isDragging) {
                          setHoveredMunicipality("");
                        }
                      }}
                    >
                      <path
                        d={zone.d}
                        className="map-zone"
                        style={hasNews ? { fill: zone.fillColor } : undefined}
                        onClick={(event) => {
                          event.stopPropagation();
                          if (!hasNews) {
                            return;
                          }
                          selectZone(zone.sourceName);
                        }}
                      >
                        <title>
                          {hasNews
                            ? `${zone.displayName}: ${zone.signals} сигналов`
                            : `${zone.displayName}: нет новостей`}
                        </title>
                      </path>
                    </g>
                  );
                })}
                {overlayLabelZone && (
                  <g className="map-label-layer">
                    <text
                      x={overlayLabelZone.x}
                      y={overlayLabelZone.y - 12}
                      className="map-zone-label map-zone-label-overlay"
                      aria-hidden="true"
                    >
                      {overlayLabelZone.labelName}
                    </text>
                  </g>
                )}
              </g>
            </svg>
          </div>

          <div className="geo-zone-strip">
            {chipList.map((item) => (
              <button
                key={item.sourceName}
                type="button"
                className={`geo-zone-chip ${selectedMunicipality === item.sourceName ? "active" : ""} ${municipalitiesWithNews.has(item.sourceName) ? "" : "no-data"}`}
                onClick={() => {
                  if (!municipalitiesWithNews.has(item.sourceName)) {
                    return;
                  }
                  selectZone(item.sourceName);
                }}
                disabled={!municipalitiesWithNews.has(item.sourceName)}
              >
                <span>{item.labelName}</span>
                <small>{item.signals}</small>
              </button>
            ))}
          </div>
        </section>

        <section className="card animate-in">
          <div className="section-head">
            <h2>Профиль территории</h2>
            <span>{selectedMunicipalityData?.labelName ?? "Не выбран"}</span>
          </div>
          <div className="geo-profile">
            <div className="geo-stats">
              <article>
                <span>Всего сигналов</span>
                <strong>{selectedMunicipalityData?.signals ?? 0}</strong>
              </article>
              <article>
                <span>Критических тем</span>
                <strong>{selectedMunicipalityData?.critical ?? 0}</strong>
              </article>
              <article>
                <span>Основная тема</span>
                <strong>{selectedMunicipalityData?.topTopic ?? "данные уточняются"}</strong>
              </article>
            </div>

            <h3>Проблемы по выбранной территории</h3>
            <div className="cards-stack">
              {municipalProblems.map((problem) => {
                const isExpanded = expandedProblemId === problem.id;
                const areaDetails = municipalProblemDetails[problem.id] ?? [];

                return (
                  <article key={problem.id} className={`geo-problem ${isExpanded ? "expanded" : ""}`}>
                    <div className="geo-problem-main">
                      <strong>{problem.title}</strong>
                      <p>{problem.summary}</p>
                    </div>
                    <div className="geo-problem-actions">
                      <div className="geo-problem-tags">
                        <Badge text={problem.sector} tone="neutral" outlined />
                        <Badge text={problem.priority} tone={getPriorityTone(problem.priority)} />
                      </div>
                      <div className="geo-problem-buttons">
                        <button
                          type="button"
                          className="ghost-button geo-problem-action"
                          onClick={() => toggleProblemDistricts(problem.id)}
                          aria-expanded={isExpanded}
                        >
                          {isExpanded ? "Скрыть детали" : "Показать по районам"}
                        </button>
                        <button
                          type="button"
                          className="secondary-button geo-problem-action"
                          onClick={() => onOpenTopic?.(problem)}
                        >
                          Подробнее
                        </button>
                      </div>
                    </div>
                    <div className={`geo-problem-areas ${isExpanded ? "open" : ""}`}>
                      <ul className="geo-problem-area-list">
                        {areaDetails.map((area) => (
                          <li key={area.id}>
                            <div className="geo-problem-area-head">
                              <strong>{area.area}</strong>
                              <Badge text={area.priority} tone={getPriorityTone(area.priority)} />
                            </div>
                            <p>{area.issue}</p>
                            <div className="geo-problem-area-meta">
                              <span>{area.sector}</span>
                              <span>Сигналов: {area.signals}</span>
                              <span>{area.status}</span>
                            </div>
                            <button
                              type="button"
                              className="ghost-button geo-problem-area-link"
                              onClick={() => onOpenTopic?.(buildAreaTopic(problem, area))}
                            >
                              Подробнее
                            </button>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </article>
                );
              })}

              {!municipalProblems.length && (
                <p className="empty-state">
                  Для выбранной территории темы из приоритетного списка не зафиксированы.
                </p>
              )}
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

