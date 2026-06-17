export type HttpRequestConfig = {
  method: string;
  url: string;
  data?: unknown;
  params?: Record<string, string>;
  headers?: Record<string, string>;
  timeout?: number;
  withCredentials?: boolean;
  responseType?: XMLHttpRequestResponseType;
};

export type HttpResponse<T> = {
  data: T;
  status: number;
  statusText: string;
  headers: () => Record<string, string>;
  config: HttpRequestConfig;
};

export async function httpRequest<T>(config: HttpRequestConfig): Promise<HttpResponse<T>> {
  let url = config.url;
  if (config.params) {
    const searchParams = new URLSearchParams();
    for (const [key, value] of Object.entries(config.params)) {
      searchParams.append(key, value);
    }
    const qs = searchParams.toString();
    if (qs) url += (url.includes('?') ? '&' : '?') + qs;
  }

  const headers: Record<string, string> = {
    Accept: 'application/json, text/plain, */*',
    ...config.headers,
  };

  if (config.data && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json;charset=utf-8';
  }

  let body: BodyInit | null = null;
  if (config.data !== undefined) {
    body = JSON.stringify(config.data);
  }

  const controller = new AbortController();
  const timeoutId = config.timeout
    ? setTimeout(() => controller.abort(), config.timeout)
    : undefined;

  try {
    const response = await fetch(url, {
      method: config.method,
      headers,
      body,
      signal: controller.signal,
      credentials: config.withCredentials ? 'include' : 'same-origin',
    });

    const contentType = response.headers.get('content-type') || '';
    let parsedData: unknown;
    if (contentType.includes('application/json')) {
      parsedData = await response.json();
    } else {
      parsedData = await response.text();
    }

    const headerMap: Record<string, string> = {};
    response.headers.forEach((value, key) => { headerMap[key] = value; });

    return {
      data: parsedData as T,
      status: response.status,
      statusText: response.statusText,
      headers: () => headerMap,
      config,
    };
  } catch (error: unknown) {
    throw {
      data: null,
      status: -1,
      statusText: (error as Error).message || 'Unknown error',
      headers: () => ({}),
      config,
      error,
    };
  } finally {
    if (timeoutId) clearTimeout(timeoutId);
  }
}

export function legacyDateFormat(date: Date | string | number, format: string): string {
  const d = typeof date === 'string' || typeof date === 'number' ? new Date(date) : date;
  if (isNaN(d.getTime())) return '';

  const pad = (n: number, width: number = 2): string => {
    const s = n.toString();
    return s.length >= width ? s : '0'.repeat(width - s.length) + s;
  };

  const tokens: Record<string, string> = {
    'yyyy': d.getFullYear().toString(),
    'yy': d.getFullYear().toString().slice(-2),
    'y': d.getFullYear().toString(),
    'MMMM': ['January', 'February', 'March', 'April', 'May', 'June',
             'July', 'August', 'September', 'October', 'November', 'December'][d.getMonth()],
    'MMM': ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
            'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][d.getMonth()],
    'MM': pad(d.getMonth() + 1),
    'M': (d.getMonth() + 1).toString(),
    'dd': pad(d.getDate()),
    'd': d.getDate().toString(),
    'EEEE': ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'][d.getDay()],
    'EEE': ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'][d.getDay()],
    'HH': pad(d.getHours()),
    'H': d.getHours().toString(),
    'hh': pad(d.getHours() % 12 || 12),
    'h': (d.getHours() % 12 || 12).toString(),
    'mm': pad(d.getMinutes()),
    'm': d.getMinutes().toString(),
    'ss': pad(d.getSeconds()),
    's': d.getSeconds().toString(),
    'sss': pad(d.getMilliseconds(), 3),
    'a': d.getHours() < 12 ? 'AM' : 'PM',
    'Z': (() => {
      const offset = d.getTimezoneOffset();
      const hours = Math.abs(Math.floor(offset / 60));
      const minutes = Math.abs(offset % 60);
      const sign = offset <= 0 ? '+' : '-';
      return `${sign}${pad(hours)}${pad(minutes)}`;
    })(),
  };

  const sortedTokens = Object.keys(tokens).sort((a, b) => b.length - a.length);
  let result = format;
  for (const token of sortedTokens) {
    const regex = new RegExp(`(?<!${token[0]})${token}(?!${token[0]})`, 'g');
    result = result.replace(regex, tokens[token]);
  }
  return result;
}

export function legacyNumberFormat(value: number | string, fractionSize?: number): string {
  if (value === null || value === undefined || value === '') return '';
  const num = typeof value === 'string' ? parseFloat(value) : value;
  if (isNaN(num)) return '';
  const frac = fractionSize !== undefined ? fractionSize : 3;
  const rounded = Math.round(num * Math.pow(10, frac)) / Math.pow(10, frac);
  const parts = rounded.toFixed(frac).split('.');
  parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  return parts.join('.');
}

export function legacyCurrencyFormat(value: number | string, symbol?: string, fractionSize?: number): string {
  const sym = symbol !== undefined ? symbol : '$';
  const formatted = legacyNumberFormat(value, fractionSize !== undefined ? fractionSize : 2);
  if (!formatted) return '';
  return sym + formatted;
}

export function legacyLimitTo<T>(input: T[] | string, limit: number): T[] | string {
  if (!input) return input;
  if (typeof input === 'string') return limit < 0 ? input.slice(limit) : input.slice(0, limit);
  return limit < 0 ? input.slice(input.length + limit) : input.slice(0, limit);
}

export function legacyOrderBy<T>(input: T[], predicates: string | string[], reverse?: boolean): T[] {
  if (!input) return [];
  const preds = Array.isArray(predicates) ? predicates : [predicates];
  const sorted = [...input];
  sorted.sort((a, b) => {
    for (const pred of preds) {
      let dir = 1;
      let key = pred;
      if (key.startsWith('-')) { dir = -1; key = key.slice(1); }
      if (key.startsWith('+')) key = key.slice(1);
      const aVal = (a as Record<string, unknown>)[key] as number;
      const bVal = (b as Record<string, unknown>)[key] as number;
      if (aVal < bVal) return -1 * dir;
      if (aVal > bVal) return 1 * dir;
    }
    return 0;
  });
  return reverse ? sorted.reverse() : sorted;
}

export function legacyFilter<T extends Record<string, unknown>>(input: T[], search: string | Record<string, unknown>): T[] {
  if (!input) return [];
  if (typeof search === 'string') {
    if (!search) return input;
    const lowerSearch = search.toLowerCase();
    return input.filter(item =>
      Object.values(item).some(val => {
        if (val === null || val === undefined) return false;
        return String(val).toLowerCase().includes(lowerSearch);
      })
    );
  }
  return input.filter(item =>
    Object.entries(search).every(([_key, value]) => Object.values(item).includes(value))
  );
}

export function legacyToJson(value: unknown): string {
  return JSON.stringify(value, (_key, val) => (val === undefined ? null : val));
}

export function legacyFromJson<T>(json: string): T {
  return JSON.parse(json) as T;
}

export function legacyCopy<T>(source: T): T {
  if (source === null || source === undefined || typeof source !== 'object') return source;
  if (source instanceof Date) return new Date(source.getTime()) as unknown as T;
  if (source instanceof RegExp) return new RegExp(source) as unknown as T;
  if (Array.isArray(source)) return source.map(item => legacyCopy(item)) as unknown as T;
  const result: Record<string, unknown> = {};
  for (const key of Object.keys(source as Record<string, unknown>)) {
    result[key] = legacyCopy((source as Record<string, unknown>)[key]);
  }
  return result as T;
}

export function legacyEquals(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if (a === null || a === undefined || b === null || b === undefined) return false;
  if (typeof a !== typeof b) return false;
  if (typeof a !== 'object') return a === b;
  if (a instanceof Date && b instanceof Date) return a.getTime() === b.getTime();
  if (a instanceof RegExp && b instanceof RegExp) return a.toString() === b.toString();
  if (Array.isArray(a) && Array.isArray(b)) {
    if (a.length !== b.length) return false;
    return a.every((val, idx) => legacyEquals(val, b[idx]));
  }
  const keysA = Object.keys(a as Record<string, unknown>);
  const keysB = Object.keys(b as Record<string, unknown>);
  if (keysA.length !== keysB.length) return false;
  return keysA.every(key => legacyEquals((a as Record<string, unknown>)[key], (b as Record<string, unknown>)[key]));
}

export type ValidationError = {
  field: string;
  message: string;
  validator: string;
};

export class LegacyFormValidator {
  private errors: ValidationError[] = [];

  required(value: unknown, field: string): boolean {
    const valid = value !== null && value !== undefined && value !== '';
    if (!valid) this.errors.push({ field, message: `${field} is required`, validator: 'required' });
    return valid;
  }

  minLength(value: string, min: number, field: string): boolean {
    const valid = !value || value.length >= min;
    if (!valid) this.errors.push({ field, message: `${field} must be at least ${min} characters`, validator: 'minlength' });
    return valid;
  }

  maxLength(value: string, max: number, field: string): boolean {
    const valid = !value || value.length <= max;
    if (!valid) this.errors.push({ field, message: `${field} must be at most ${max} characters`, validator: 'maxlength' });
    return valid;
  }

  pattern(value: string, regex: RegExp, field: string): boolean {
    const valid = !value || regex.test(value);
    if (!valid) this.errors.push({ field, message: `${field} does not match the required pattern`, validator: 'pattern' });
    return valid;
  }

  email(value: string, field: string): boolean {
    const emailRegex = /^[a-z0-9!#$%&'*+/=?^_`{|}~.-]+@[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)*$/i;
    return this.pattern(value, emailRegex, field);
  }

  number(value: unknown, field: string): boolean {
    const valid = value === null || value === undefined || (typeof value === 'number' && !isNaN(value));
    if (!valid) this.errors.push({ field, message: `${field} must be a number`, validator: 'number' });
    return valid;
  }

  min(value: number, min: number, field: string): boolean {
    const valid = value === null || value === undefined || value >= min;
    if (!valid) this.errors.push({ field, message: `${field} must be at least ${min}`, validator: 'min' });
    return valid;
  }

  max(value: number, max: number, field: string): boolean {
    const valid = value === null || value === undefined || value <= max;
    if (!valid) this.errors.push({ field, message: `${field} must be at most ${max}`, validator: 'max' });
    return valid;
  }

  getErrors(): ValidationError[] { return [...this.errors]; }
  hasErrors(): boolean { return this.errors.length > 0; }
  clear(): void { this.errors = []; }
  getSummary(): string { return this.errors.map(e => `${e.field}: ${e.message}`).join('\n'); }
}
