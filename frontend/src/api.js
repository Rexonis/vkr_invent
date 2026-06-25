// API-клиент фронтенда: выполняет запросы к backend и унифицирует обработку ошибок.
/**
 * Разбирает ответ API и приводит ошибки backend к понятному сообщению для пользователя.
 */
async function parse(response) {
  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    const title = typeof data === "string" ? data.match(/<title>(.*?)<\/title>/is)?.[1] : "";
    const text = typeof data === "string" ? data.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim() : "";
    const detail = data?.error || title || text;
    const error = new Error(detail ? `Запрос не выполнен: ${detail}` : "Запрос не выполнен");
    error.status = response.status;
    throw error;
  }
  return data;
}

/**
 * Выполняет HTTP-запрос с таймаутом и единым текстом сетевых ошибок.
 */
function request(url, options = {}) {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 8000);
  return fetch(url, { ...options, signal: controller.signal })
    .catch((err) => {
      if (err?.name === "AbortError") {
        throw new Error("Нет ответа от сервера. Проверьте, что backend запущен на 192.168.157.249:5500 и база данных доступна.");
      }
      if (err instanceof TypeError) {
        throw new Error("Не удалось подключиться к API. Запустите backend и проверьте HTTPS-сертификат для 192.168.157.249:5500.");
      }
      throw err;
    })
    .finally(() => window.clearTimeout(timeout));
}

export const api = {
  get(url) {
    return request(url, { credentials: "include" }).then(parse);
  },
  send(url, method, body = {}) {
    return request(url, {
      method,
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(parse);
  },
};
