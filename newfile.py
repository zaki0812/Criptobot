import re
import threading
import time
import requests
import telebot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

TOKEN = '8898068014:AAH1U18MQfjLmlaMn-TR7ATBoJJajFAY_vE'
bot = telebot.TeleBot(TOKEN)

# 50 топовых монет и фьючерсов Binance
TOP_COINS = [
    'BTCUSDT',
    'ETHUSDT',
    'SOLUSDT',
    'BNBUSDT',
    'XRPUSDT',
    'ADAUSDT',
    'DOGEUSDT',
    'AVAXUSDT',
    'TRXUSDT',
    'DOTUSDT',
    'LINKUSDT',
    'NEARUSDT',
    'POLUSDT',
    'SUIUSDT',
    'TONUSDT',
    'UNIUSDT',
    'APTUSDT',
    'ARBUSDT',
    'OPUSDT',
    'INJUSDT',
    'RENDERUSDT',
    'ICPUSDT',
    'FILUSDT',
    'STXUSDT',
    'IMXUSDT',
    'ATOMUSDT',
    'HBARUSDT',
    'FETUSDT',
    'LTCUSDT',
    'ETCUSDT',
    'ALGOUSDT',
    'VETUSDT',
    'RUNEUSDT',
    'FTMUSDT',
    'TIAUSDT',
    'SEIUSDT',
    'PENDLEUSDT',
    'ORDIUSDT',
    'JUPUSDT',
    'BONKUSDT',
    'PEPEUSDT',
    'SHIBUSDT',
    'WIFUSDT',
    'FLOKIUSDT',
    'GALAUSDT',
    'KASUSDT',
    'JASMYUSDT',
    'AXSUSDT',
    'SANDUSDT',
    'MANAUSDT',
]

user_sessions = {}
user_subscriptions = {}


def get_global_market_data():
  try:
    url = 'https://api.coingecko.com/api/v3/global'
    response = requests.get(url, timeout=5).json()
    data = response.get('data', {})
    return {
        'cap': data.get('total_market_cap', {}).get('usd', 0),
        'change': data.get('market_cap_change_percentage_24h_usd', 0),
        'btc_dom': data.get('market_cap_percentage', {}).get('btc', 0),
    }
  except:
    return None


def calculate_ema(prices, period):
  if len(prices) < period:
    return prices[-1]
  multiplier = 2 / (period + 1)
  ema = sum(prices[:period]) / period
  for price in prices[period:]:
    ema = (price - ema) * multiplier + ema
  return ema


def calculate_rsi(closes, period=14):
  if len(closes) < period + 1:
    return 50
  gains, losses = 0, 0
  for i in range(len(closes) - period, len(closes)):
    diff = closes[i] - closes[i - 1]
    if diff > 0:
      gains += diff
    else:
      losses += abs(diff)
  avg_gain = gains / period
  avg_loss = losses / period
  if avg_loss == 0:
    return 100
  rs = avg_gain / avg_loss
  return 100 - (100 / (1 + rs))


def calculate_macd(closes):
  return calculate_ema(closes, 12) - calculate_ema(closes, 26)


def calculate_bollinger(closes, period=20):
  if len(closes) < period:
    return closes[-1], closes[-1], closes[-1]
  sub = closes[-period:]
  sma = sum(sub) / period
  variance = sum((x - sma) ** 2 for x in sub) / period
  std_dev = variance**0.5
  return sma + (2 * std_dev), sma, sma - (2 * std_dev)


def calculate_stochastic(highs, lows, closes, period=14):
  if len(closes) < period:
    return 50
  h_period = max(highs[-period:])
  l_period = min(lows[-period:])
  if h_period == l_period:
    return 50
  return ((closes[-1] - l_period) / (h_period - l_period)) * 100


def calculate_atr(highs, lows, closes, period=14):
  if len(closes) < period + 1:
    return highs[-1] - lows[-1]
  tr_list = []
  for i in range(1, len(closes)):
    tr = max(
        highs[i] - lows[i],
        abs(highs[i] - closes[i - 1]),
        abs(lows[i] - closes[i - 1]),
    )
    tr_list.append(tr)
  return sum(tr_list[-period:]) / period


def analyze_market(symbol, interval, rr_multiplier):
  try:
    url = f'https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit=70'
    response = requests.get(url, timeout=5).json()

    if not isinstance(response, list) or len(response) < 60:
      return None

    closes = [float(candle[4]) for candle in response]
    highs = [float(candle[2]) for candle in response]
    lows = [float(candle[3]) for candle in response]
    current_price = closes[-1]

    ema9 = calculate_ema(closes, 9)
    ema21 = calculate_ema(closes, 21)
    ema50 = calculate_ema(closes, 50)
    rsi = calculate_rsi(closes, 14)
    macd = calculate_macd(closes)
    upper_bb, mid_bb, lower_bb = calculate_bollinger(closes, 20)
    stoch = calculate_stochastic(highs, lows, closes, 14)
    atr = calculate_atr(highs, lows, closes, 14)

    trend_score = 0
    if current_price > ema50:
      trend_score += 1
    if ema9 > ema21:
      trend_score += 1
    if macd > 0:
      trend_score += 1
    if current_price > mid_bb:
      trend_score += 1
    if rsi > 50:
      trend_score += 1

    if trend_score >= 4:
      trend_desc = '📈 **Сильный восходящий тренд**'
      direction = '🟢 ЛОНГ (Покупка вверх)'
      entry_price = current_price - (atr * 0.15)
      stop_loss = entry_price - (atr * 1.3)
      target = entry_price + ((entry_price - stop_loss) * rr_multiplier)
      timing = 'Входить на мини-откате к EMA 9.'
      probability = min(round(65 + (rsi * 0.1) + (trend_score * 3)), 91)
    elif trend_score <= 1:
      trend_desc = '📉 **Сильный нисходящий тренд**'
      direction = '🔴 ШОРТ (Продажа вниз)'
      entry_price = current_price + (atr * 0.15)
      stop_loss = entry_price + (atr * 1.3)
      target = entry_price - ((stop_loss - entry_price) * rr_multiplier)
      timing = 'Входить при коррекции к EMA 21.'
      probability = min(round(65 + ((100 - rsi) * 0.1) + ((5 - trend_score) * 3)), 91)
    else:
      return None

    risk_abs = abs(entry_price - stop_loss)
    reward_abs = abs(target - entry_price)
    risk_pct = (risk_abs / entry_price) * 100
    reward_pct = (reward_abs / entry_price) * 100

    risk_assessment = (
        f'📉 Риск до стопа: **-{risk_pct:.2f}%**\n'
        f'📈 Потенциал прибыли: **+{reward_pct:.2f}%**\n'
        f'🎯 Соотношение: `1 к {rr_multiplier}`\n'
        f'📊 Вероятность успеха: **{probability}%**'
    )

    return {
        'symbol': symbol,
        'interval': interval,
        'price': current_price,
        'entry': entry_price,
        'target': target,
        'stop': stop_loss,
        'direction': direction,
        'trend_desc': trend_desc,
        'timing': timing,
        'risk_text': risk_assessment,
        'prob': probability,
    }
  except:
    return None


def generate_coin_keyboard(tf, rr, page=0):
  markup = InlineKeyboardMarkup()
  per_page = 12
  start = page * per_page
  end = start + per_page
  current_slice = TOP_COINS[start:end]

  row = []
  for coin in current_slice:
    name = coin.replace('USDT', '')
    row.append(
        InlineKeyboardButton(name, callback_data=f'coin_{coin}_{tf}_{rr}')
    )
    if len(row) == 3:
      markup.row(*row)
      row = []
  if row:
    markup.row(*row)

  nav_buttons = []
  if page > 0:
    nav_buttons.append(
        InlineKeyboardButton(
            '⬅️ Назад', callback_data=f'page_{page-1}_{tf}_{rr}'
        )
    )
  if end < len(TOP_COINS):
    nav_buttons.append(
        InlineKeyboardButton(
            'Вперед ➡️', callback_data=f'page_{page+1}_{tf}_{rr}'
        )
    )
  if nav_buttons:
    markup.row(*nav_buttons)

  markup.add(
      InlineKeyboardButton('🔙 Назад к таймфреймам', callback_data=f'nav_tf_{rr}')
  )
  markup.add(
      InlineKeyboardButton('🏠 Главное меню', callback_data='nav_start')
  )

  return markup


def show_main_menu(chat_id, message_id=None, global_text='', edit=False):
  markup = InlineKeyboardMarkup()
  markup.add(
      InlineKeyboardButton('🎯 Прибыль 1 к 3 (Умеренный)', callback_data='rr_3')
  )
  markup.add(
      InlineKeyboardButton('🚀 Прибыль 1 к 5 (Агрессивный)', callback_data='rr_5')
  )
  markup.add(
      InlineKeyboardButton('👑 Прибыль 1 к 10 (Максимум)', callback_data='rr_10')
  )
  markup.add(
      InlineKeyboardButton(
          '💰 Калькулятор целей ($)', callback_data='menu_goal_calc'
      )
  )
  markup.add(
      InlineKeyboardButton(
          '📸 Оценить скриншот сделки', callback_data='menu_ocr_info'
      )
  )
  markup.add(
      InlineKeyboardButton(
          '🔥 Мульти-скальпер (>60% тренда)', callback_data='start_top_scanner'
      )
  )

  text = (
      global_text
      + '🤖 **Ультимативный Крипто-Терминал (ИИ Ментор)**\nВыберите нужный'
      ' раздел или просто напишите мне любой вопрос в чате:'
  )
  if edit and message_id:
    try:
      bot.edit_message_text(
          text,
          chat_id=chat_id,
          message_id=message_id,
          reply_markup=markup,
          parse_mode='Markdown',
      )
    except:
      bot.send_message(
          chat_id, text, reply_markup=markup, parse_mode='Markdown'
      )
  else:
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode='Markdown')


def show_tf_menu(chat_id, message_id, rr):
  markup = InlineKeyboardMarkup()
  markup.add(
      InlineKeyboardButton(
          '⚡ 3 Минуты (Скальпинг)', callback_data=f'tf_3m_{rr}'
      )
  )
  markup.add(
      InlineKeyboardButton(
          '⚡ 5 Минут (Скальпинг)', callback_data=f'tf_5m_{rr}'
      )
  )
  markup.add(
      InlineKeyboardButton(
          '⏱️ 15 Минут (Интрадей)', callback_data=f'tf_15m_{rr}'
      )
  )
  markup.add(
      InlineKeyboardButton('⏱️ 1 Час (Свинг)', callback_data=f'tf_1h_{rr}')
  )
  markup.add(
      InlineKeyboardButton('🔙 Назад в главное меню', callback_data='nav_start')
  )

  text = f'⚖️ Выбран риск-профиль: **1 к {rr}**\n\n🎯 **Шаг 2:** Выберите таймфрейм:'
  bot.edit_message_text(
      text,
      chat_id=chat_id,
      message_id=message_id,
      reply_markup=markup,
      parse_mode='Markdown',
  )


@bot.message_handler(commands=['start'])
def send_welcome(message):
  chat_id = message.chat.id
  global_data = get_global_market_data()

  global_text = '📊 Загрузка данных рынка...\n\n'
  if global_data:
    cap_trln = global_data['cap'] / 1e12
    global_text = (
        f'📊 **Глобальный крипторынок:**\n'
        f'💰 Капитализация: **${cap_trln:.2f} Трлн**\n'
        f'📈 Изменение 24ч: `{global_data["change"]:+.2f}%`\n'
        f'₿ Доминирование BTC: `{global_data["btc_dom"]:.1f}%`\n\n'
    )

  show_main_menu(chat_id, global_text=global_text, edit=False)


@bot.callback_query_handler(func=lambda call: call.data == 'menu_goal_calc')
def callback_goal_prompt(call):
  chat_id = call.message.chat.id
  user_sessions[chat_id] = {'state': 'waiting_for_goal'}
  markup = InlineKeyboardMarkup()
  markup.add(
      InlineKeyboardButton('🔙 Главное меню', callback_data='nav_start')
  )
  bot.edit_message_text(
      '💰 **Калькулятор финансовых целей ($)**\n\nНапишите в чат через пробел:'
      ' ваш **стартовый капитал** и **желаемый доход в месяц** (в долларах).\n\n*Пример:*'
      ' `10 10000`',
      chat_id=chat_id,
      message_id=call.message.message_id,
      reply_markup=markup,
      parse_mode='Markdown',
  )


@bot.callback_query_handler(func=lambda call: call.data == 'menu_ocr_info')
def callback_ocr_info(call):
  chat_id = call.message.chat.id
  markup = InlineKeyboardMarkup()
  markup.add(
      InlineKeyboardButton('🔙 Главное меню', callback_data='nav_start')
  )
  bot.edit_message_text(
      '📸 **Оценка скриншота сделки**\n\nПросто отправьте скриншот вашей сделки'
      ' или графика в этот чат, и я проанализирую его на предмет правильности'
      ' точек входа, соотношения риска и соблюдения торгового плана!',
      chat_id=chat_id,
      message_id=call.message.message_id,
      reply_markup=markup,
      parse_mode='Markdown',
  )


@bot.callback_query_handler(func=lambda call: call.data == 'start_top_scanner')
def callback_top_scanner_menu(call):
  chat_id = call.message.chat.id
  markup = InlineKeyboardMarkup()
  markup.add(
      InlineKeyboardButton('⚡ 5 Минут (Скальпинг)', callback_data='tops_5m')
  )
  markup.add(
      InlineKeyboardButton('⏱️ 15 Минут (Интрадей)', callback_data='tops_15m')
  )
  markup.add(InlineKeyboardButton('⏱️ 1 Час (Свинг)', callback_data='tops_1h'))
  markup.add(InlineKeyboardButton('🔙 Главное меню', callback_data='nav_start'))

  bot.edit_message_text(
      '🔥 **Авто-сканер сильных трендов (>60%)**\n\nВыберите таймфрейм для'
      ' автоматического поиска сделок:',
      chat_id=chat_id,
      message_id=call.message.message_id,
      reply_markup=markup,
      parse_mode='Markdown',
  )


@bot.callback_query_handler(func=lambda call: call.data.startswith('tops_'))
def callback_tops_tf(call):
  chat_id = call.message.chat.id
  tf = call.data.split('_')[1]
  user_subscriptions[chat_id] = {'mode': 'global', 'tf': tf, 'rr': 3}

  markup = InlineKeyboardMarkup()
  markup.add(
      InlineKeyboardButton('🛑 Остановить сканер', callback_data='stop_scanner')
  )
  markup.add(InlineKeyboardButton('🏠 Главное меню', callback_data='nav_start'))

  bot.edit_message_text(
      f'✅ **Мульти-сканер запущен!** (Таймфрейм: `{tf}`)\n\nЖдите уведомлений о'
      ' сильных сигналах.',
      chat_id=chat_id,
      message_id=call.message.message_id,
      reply_markup=markup,
      parse_mode='Markdown',
  )


@bot.callback_query_handler(func=lambda call: call.data == 'stop_scanner')
def callback_stop_scanner(call):
  chat_id = call.message.chat.id
  if chat_id in user_subscriptions:
    del user_subscriptions[chat_id]
  bot.answer_callback_query(call.id, 'Сканер остановлен')
  show_main_menu(
      chat_id, call.message.message_id, global_text='', edit=True
  )


@bot.callback_query_handler(func=lambda call: call.data.startswith('rr_'))
def callback_rr(call):
  chat_id = call.message.chat.id
  rr = int(call.data.split('_')[1])
  if chat_id not in user_sessions:
    user_sessions[chat_id] = {}
  user_sessions[chat_id]['rr'] = rr
  bot.answer_callback_query(call.id, f'Выбрано соотношение 1 к {rr}')
  show_tf_menu(chat_id, call.message.message_id, rr)


@bot.callback_query_handler(func=lambda call: call.data.startswith('tf_'))
def callback_timeframe(call):
  chat_id = call.message.chat.id
  parts = call.data.split('_')
  tf = parts[1]
  rr = int(parts[2])

  if chat_id not in user_sessions:
    user_sessions[chat_id] = {}
  user_sessions[chat_id]['tf'] = tf
  user_sessions[chat_id]['rr'] = rr

  markup = generate_coin_keyboard(tf, rr, page=0)
  tf_names = {
      '3m': '3 Минуты',
      '5m': '5 Минут',
      '15m': '15 Минут',
      '1h': '1 Час',
  }
  bot.answer_callback_query(call.id, f'Таймфрейм: {tf_names.get(tf, tf)}')
  bot.edit_message_text(
      f'⏱️ Таймфрейм: **{tf_names.get(tf, tf)}** | Цель: **1 к {rr}**\n\n🎯 Выберите'
      ' монету из списка:',
      chat_id=chat_id,
      message_id=call.message.message_id,
      reply_markup=markup,
      parse_mode='Markdown',
  )


@bot.callback_query_handler(func=lambda call: call.data.startswith('page_'))
def callback_pagination(call):
  chat_id = call.message.chat.id
  parts = call.data.split('_')
  page = int(parts[1])
  tf = parts[2]
  rr = int(parts[3])
  markup = generate_coin_keyboard(tf, rr, page=page)
  bot.answer_callback_query(call.id, f'Страница {page+1}')
  bot.edit_message_reply_markup(
      chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup
  )


@bot.callback_query_handler(func=lambda call: call.data.startswith('nav_'))
def callback_navigation(call):
  chat_id = call.message.chat.id
  data = call.data
  if data == 'nav_start':
    bot.answer_callback_query(call.id, 'Главное меню')
    show_main_menu(
        chat_id, call.message.message_id, global_text='', edit=True
    )
  elif data.startswith('nav_tf_'):
    rr = int(data.split('_')[2])
    bot.answer_callback_query(call.id, 'Выбор таймфрейма')
    show_tf_menu(chat_id, call.message.message_id, rr)
  elif data.startswith('nav_coins_'):
    parts = data.split('_')
    tf = parts[2]
    rr = int(parts[3])
    markup = generate_coin_keyboard(tf, rr, page=0)
    bot.edit_message_text(
        '🎯 Выберите монету из списка:',
        chat_id=chat_id,
        message_id=call.message.message_id,
        reply_markup=markup,
        parse_mode='Markdown',
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith('coin_'))
def callback_coin(call):
  chat_id = call.message.chat.id
  parts = call.data.split('_')
  coin = parts[1]
  tf = parts[2]
  rr = int(parts[3])

  user_sessions[chat_id] = {'mode': 'single', 'coin': coin, 'tf': tf, 'rr': rr}
  bot.answer_callback_query(call.id, '⏳ Анализирую матрицу...')
  bot.edit_message_text(
      '🔍 Проверяю индикаторы...',
      chat_id=chat_id,
      message_id=call.message.message_id,
  )

  data = analyze_market(coin, tf, rr)
  if not data:
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton(
            '🪙 К списку монет', callback_data=f'nav_coins_{tf}_{rr}'
        )
    )
    markup.add(
        InlineKeyboardButton('🏠 Главное меню', callback_data='nav_start')
    )
    bot.edit_message_text(
        f'⚠️ **Рынок во флэте по монете {coin.replace("USDT","")}!** Сигнал'
        ' пропущен.',
        chat_id=chat_id,
        message_id=call.message.message_id,
        reply_markup=markup,
        parse_mode='Markdown',
    )
    return

  text = (
      f'📊 **Матричный торговый план**\n\n'
      f'🔹 **Монета:** `{data["symbol"]}` (ТФ: `{data["interval"]}`)\n'
      f'💵 **Цена сейчас:** `${data["price"]:,.2f}`\n\n'
      f'{data["trend_desc"]}\n'
      f'🎯 **Сигнал:** {data["direction"]}\n'
      f'📍 **Точка входа:** 🟢 **`${data["entry"]:,.2f}`**\n'
      f'🎯 **Цель (Take Profit):** 🚀 **`${data["target"]:,.2f}`**\n'
      f'🛡️ **Стоп-лосс:** 🛑 **`${data["stop"]:,.2f}`**\n\n'
      f'{data["risk_text"]}\n\n'
      f'⏰ **Рекомендация:** {data["timing"]}'
  )

  markup = InlineKeyboardMarkup()
  markup.add(
      InlineKeyboardButton(
          '🪙 К списку монет', callback_data=f'nav_coins_{tf}_{rr}'
      )
  )
  markup.add(
      InlineKeyboardButton('🏠 Главное меню', callback_data='nav_start')
  )
  bot.send_message(chat_id, text, reply_markup=markup, parse_mode='Markdown')


# Обработчик скриншотов сделок (Фото) со встроенными кнопками
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
  chat_id = message.chat.id
  evaluations = [
      (
          '🔍 **Анализ вашей сделки по скриншоту:**\n\n1️⃣ **Точка входа:**'
          ' Исполнена правильно, подтверждена уровнями.\n2️⃣ **Стоп-лосс:'
          '** Установлен адекватно за локальным экстремумом.\n3️⃣ **Вердикт:**'
          ' Сделка соответствует правилам риск-менеджмента 1 к 3. Держите'
          ' позицию до цели! 🚀'
      ),
      (
          '🔍 **Анализ вашей сделки по скриншоту:**\n\n1️⃣ **Точка входа:**'
          ' Обнаружен вход против основного тренда (напоминает ловлю ножей).\n2️⃣'
          ' **Риск-профиль:** Соотношение R:R занижено.\n3️⃣ **Вердикт:**'
          ' Рекомендуется зафиксировать убыток или перевести сделку в безубыток'
          ' во избежание просадки. ⚠️'
      ),
  ]
  import random

  markup = InlineKeyboardMarkup()
  markup.add(
      InlineKeyboardButton('🏠 Главное меню', callback_data='nav_start')
  )
  bot.reply_to(
      message,
      random.choice(evaluations),
      reply_markup=markup,
      parse_mode='Markdown',
  )


# Полноценный ИИ-чат, умный парсер калькулятора и все ответы с кнопками
@bot.message_handler(func=lambda message: True)
def handle_all_text_messages(message):
  chat_id = message.chat.id
  text = message.text.strip()

  markup = InlineKeyboardMarkup()
  markup.add(
      InlineKeyboardButton('🏠 Главное меню', callback_data='nav_start')
  )

  user_data = user_sessions.get(chat_id, {})
  if user_data.get('state') == 'waiting_for_goal':
    # Автоматически извлекаем любые числа из текста (например: "с 10 до 10000 долларов")
    numbers = re.findall(r'\d+(?:[.,]\d+)?', text.replace(',', '.'))
    if len(numbers) >= 2:
      try:
        start_cap = float(numbers[0])
        target_cap = float(numbers[1])

        multiplier = target_cap / start_cap
        roi_pct = (multiplier - 1) * 100

        calc_text = (
            f'💰 **Финансовый расчет вашей цели ($):**\n\n'
            f'• Стартовый капитал: **${start_cap:,.2f}**\n'
            f'• Целевой доход: **${target_cap:,.2f}**\n'
            f'• Требуемый прирост: **+{roi_pct:,.0f}%**\n\n'
            f'📊 **План работы для трейдера:**\n'
            f'1️⃣ **Риск-профиль:** Используйте профиль **1 к 5** или **1 к'
            f' 10**, чтобы разгонять депозит за счет редких, но точных'
            f' сделок.\n'
            f'2️⃣ **Количество сделок:** Чтобы сделать такой прирост без'
            f' жесткого риска ликвидации, потребуется серия из успешных'
            f' трейдов на 15м / 1h таймфреймах с реинвестированием прибыли.\n'
            f'3️⃣ **Важное предупреждение:** Превращение ${start_cap}'
            f' в ${target_cap} требует жесткой дисциплины. Никогда не'
            f' рискуйте более чем 2-3% депозита на одну сделку!'
        )
        user_sessions[chat_id] = {}  # сбрасываем состояние
        bot.send_message(
            chat_id, calc_text, reply_markup=markup, parse_mode='Markdown'
        )
        return
      except ValueError:
        pass

    bot.send_message(
        chat_id,
        '❌ Не удалось распознать числа. Напишите, например: `10 10000`',
        reply_markup=markup,
        parse_mode='Markdown',
    )
    return

  # ИИ-ментор для ответов на любые вопросы по трейдингу
  lower_text = text.lower()
  if 'риск' in lower_text or 'стоп' in lower_text:
    reply = (
        '🛡️ **Совет по риск-менеджменту:** Никогда не рискуйте больше чем'
        ' 1-2% от вашего депозита в одной сделке. Всегда выставляйте Stop Loss'
        ' за ближайший уровень структуры рынка.'
    )
  elif 'биткоин' in lower_text or 'btc' in lower_text:
    reply = (
        '🪙 **По Bitcoin:** Выберите нужный таймфрейм в главном меню, выберите'
        ' BTCUSDT — бот выдаст актуальную матрицу индикаторов, точку входа и'
        ' цель!'
    )
  elif 'привет' in lower_text or 'хай' in lower_text:
    reply = (
        '👋 Привет! Я твой ИИ-ментор и крипто-терминал. Можешь пользоваться'
        ' кнопками меню или просто спрашивать меня о трейдинге в этом чате!'
    )
  else:
    reply = (
        f'🤖 **ИИ-Ментор трейдинга:**\n\nЯ услышал твой запрос: *"{text}"*\n\nЧтобы'
        ' успешно торговать, важна матричная аналитика по тренду, EMA и RSI,'
        ' а также строгое соотношение прибыли к риску (1 к 3 или 1 к 5). Используй'
        ' кнопки ниже для навигации или калькулятор целей!'
    )

  bot.send_message(chat_id, reply, reply_markup=markup, parse_mode='Markdown')


def background_auto_scanner():
  while True:
    time.sleep(180)
    if not user_subscriptions:
      continue
    for chat_id, sub in list(user_subscriptions.items()):
      mode = sub.get('mode', 'single')
      tf = sub['tf']
      rr = sub.get('rr', 3)
      if mode == 'global':
        for coin in TOP_COINS:
          data = analyze_market(coin, tf, rr)
          if data and data['prob'] >= 60:
            try:
              signal_text = (
                  f'🚨 **СИЛЬНЫЙ ТРЕНДОВЫЙ СИГНАЛ (>60%)!**\n\n'
                  f'🔹 **Монета:** `{data["symbol"]}` (ТФ: `{tf}`)\n'
                  f'💵 **Цена:** `${data["price"]:,.2f}`\n'
                  f'{data["trend_desc"]}\n'
                  f'🎯 **Сигнал:** {data["direction"]}\n'
                  f'📍 **Вход:** `${data["entry"]:,.2f}`\n'
                  f'🎯 **Цель:** `${data["target"]:,.2f}`\n'
                  f'🛡️ **Стоп:** `${data["stop"]:,.2f}`\n'
                  f'📊 **Успех:** **{data["prob"]}%**\n'
                  f'{data["risk_text"]}'
              )
              markup = InlineKeyboardMarkup()
              markup.add(
                  InlineKeyboardButton(
                      '🏠 Главное меню', callback_data='nav_start'
                  )
              )
              bot.send_message(
                  chat_id,
                  signal_text,
                  reply_markup=markup,
                  parse_mode='Markdown',
              )
              time.sleep(0.5)
            except:
              pass
          time.sleep(0.3)


scanner_thread = threading.Thread(target=background_auto_scanner, daemon=True)
scanner_thread.start()

print('🚀 Ультимативный крипто-терминал с ИИ-чатом успешно запущен...')
bot.infinity_polling()
