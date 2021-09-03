# Python 3.9.6
# Flask 2.0.1
# Flaskの公式ドキュメント：https://flask.palletsprojects.com/en/2.0.x/
# python3の公式ドキュメント：https://docs.python.org/ja/3.9/
# python3の基礎文法のわかりやすいサイト：https://note.nkmk.me/python/

# 使用するモジュールのインポート
from flask import Flask
from flask import request
from flask import json
from logging import getLogger, FileHandler, DEBUG, Formatter
from linebot import LineBotApi, WebhookHandler
from linebot.models import ( 
		MessageEvent, PostbackEvent,
		TextMessage, TextSendMessage, TemplateSendMessage,
		ButtonsTemplate, CarouselTemplate, CarouselColumn,
		PostbackTemplateAction,PostbackAction,MessageAction,URIAction,FlexSendMessage
		)
from neo4j import GraphDatabase, basic_auth
import random
import config

# Flaskクラスをnewしてappに代入
# gunicornの起動コマンドに使用しているのでここは変更しないこと
app = Flask(__name__)

# ログの設定
logger = getLogger(__name__)
logger.setLevel(DEBUG)
handler = FileHandler(filename='/var/log/intern1/flask.log')

handler.setLevel(DEBUG)
handler.setFormatter(Formatter("%(asctime)s: %(levelname)s: %(pathname)s: line %(lineno)s: %(message)s"))
logger.addHandler(handler)

# 定数
CHANNEL_ACCESS_TOKEN = config.CHANNEL_ACCESS_TOKEN
NEO4JURL = config.NEO4JURL
NEO4JID = config.NEO4JID
NEO4JPW = config.NEO4JPW
BOOKLISTNUM = 3
# グローバル変数の定義
# ユーザーが選択肢で本を選んだ回数
count_choose = 0 

# 「/」にPOSTリクエストが来た場合、index関数が実行される
@app.route('/', methods=['post'])
def index():
	# メッセージデータの解析
	data = request.data.decode('utf-8') 
	data = json.loads(data)

	# neo4jにアクセス
	driver = GraphDatabase.driver(NEO4JURL, auth=(NEO4JID,NEO4JPW))
	session = driver.session()

	# Webhookの検証用(検証用データはeventが空)
	if not data['events']:
		return '', 200

	# 返信用アクセスデータの設定
	line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
	replyToken = data['events'][0]['replyToken']

	# 本の探索を一定数以上行った時の挙動
	global count_choose
	count_choose+=1
	logger.info(str(count_choose) + "回目の検索")
	if count_choose >= 5:
		logger.info("===検索回数が指定回数を超えたので、他のことをするよう提案===")
		count_choose = 0
		# 適当なサイトへのリンクを貼る
		carousel_template_message = makereply_much_search()
		line_bot_api.reply_message(replyToken, carousel_template_message)
		return '', 200

	# ユーザーが選択肢から本のタイトルを選択
	if data['events'][0]['type'] == 'postback':
		logger.info("===Postback hello===")
		#　本を読んでいる人のIDを取る
		now_book = data['events'][0]['postback']['data']
		options = query_get_id(now_book)
		idlist = session.write_transaction(exec_get_id,options)
		# 取得したIDの人が読む本、その本が何人に読まれているか
		book_count = {}
		for id in idlist:
			# idが読んでいる本を取得する
			options = query_get_booklist(id)
			booklist = session.write_transaction(exec_get_booklist, options)
			for next_book in booklist:
				if next_book == now_book: continue
				if next_book in book_count:
					book_count[next_book] = book_count[next_book]+1
				else:
					book_count[next_book] = 1
		
		# 読まれた数が多いもの３件をユーザーに提示する
		num = 0
		booklist_for_reply = []
		for k, v in sorted(book_count.items(), key=lambda x: -x[1]):
			num += 1
			booklist_for_reply.append(k)
			logger.info("本["+k+"]は、"+str(v)+"人に読まれている")
			if num >= BOOKLISTNUM: break
		logger.info(now_book)
		carousel_template_message = makereply_popular(booklist_for_reply)
		logger.info("===よく読まれている本BOOKLISTNUM件を表示するメッセージの作成完了===")
		line_bot_api.reply_message(replyToken, carousel_template_message)
		return '', 200
	
	# ユーザーから検索ワードを受けた時の挙動
	message = data['events'][0]['message']['text']

	# 似ているタイトルをランダムに3つユーザーに提供する
	options = query_get_similar_title(message)
	titleList = session.write_transaction(exec_get_similar_title, options)
	booklist_for_reply = []
	for i in range(BOOKLISTNUM):
		booklist_for_reply.append(random.choice(titleList))
	carousel_template_message = makereply_similar_title(booklist_for_reply)
	line_bot_api.reply_message(replyToken, carousel_template_message)
	return '',200
	
def makereply_much_search():
	# URIActionは同じコードで使い回す
	labelist = ["AtCoderを始める","トビラシステムズ","Bot製作者の日記"]
	urilist = [
			"https://atcoder.jp/contests/APG4b",
			"https://tobila.com/recruit/workstyle/",
			"https://iloveconviniboshi.hatenablog.com/"]
	actionslist = []
	for i in range(BOOKLISTNUM):
		action = URIAction(
			label = labelist[i],
			uri = urilist[i]
			)
		actionslist.append(action)

	# 返信メッセージ作成
	carousel_template_message = TemplateSendMessage(
		alt_text='いつまで本について調べてるんですか？',
		template=CarouselTemplate(
			columns=[
			CarouselColumn(
				title='本について調べるのは飽きました',
				text='検索したいワードを選んでください',
				# リンク先はなんでも良い
				actions=actionslist
				)
				]
				)
	)
	return carousel_template_message

def query_get_id(title):
	ret = "MATCH (n:User)-[:read]->(b:Book)  WHERE b.title = " + '"'+ title + '"' +  " RETURN n,b"
	return ret

def exec_get_id(tx, options):
	id_list = []
	# optionsで指定した本を読んだ人のIDのリスト
	result = tx.run(options)
	#logger.info(result.keys())
	retlist = result.data('n')
	for record in retlist:
		id = record['n']['user_id']
		id_list.append(id)
	return id_list

def query_get_booklist(id):
	ret = "MATCH (n:User)-[:read]->(b:Book) where n.user_id ="
	ret += str(id)
	ret += "return n, b "
	return ret

def exec_get_booklist(tx, options):
	result = tx.run(options)
	ret = []
	flist = result.data('b')
	for record in flist:
		ret.append(record['b']['title'])
	return ret

def makereply_popular(booklist_for_reply):
	actionslist = []
	for i in range(BOOKLISTNUM):
		action = PostbackAction(
			label = booklist_for_reply[i][0:20],
			display_text = booklist_for_reply[i],
			data = booklist_for_reply[i]
			)
		actionslist.append(action)
	carousel_template_message = TemplateSendMessage(
			alt_text= 'おすすめする本のリスト',
			template=CarouselTemplate(
				columns=[
				CarouselColumn(
					title= '選択した本を読んだ人は、こんな本も読んでるよ',
					text='気になるタイトルを選んでください',
					actions=actionslist
					)
					]
					)
	)
	return carousel_template_message

def query_get_similar_title(title):
	ret = "MATCH (b:Book) WHERE b.title CONTAINS " + '"'+ title + '"' +  " RETURN b"
	return ret

def exec_get_similar_title(tx, options):
	result = tx.run(options)
	ret = []
	flist = result.data('b')
	for record in flist:
		ret.append(record['b']['title'])
	return ret

def makereply_similar_title(booklist_for_reply):
	# CarouselColumnのactionsはループでかけるためそうする
	actionslist=[]
	for i in range(BOOKLISTNUM):
		action = PostbackAction(
			label = booklist_for_reply[i][0:20],
			display_text = booklist_for_reply[i],
			data = booklist_for_reply[i]
			)
		actionslist.append(action)

	carousel_template_message = TemplateSendMessage(
			alt_text='気になる本を選んでください！',
			template=CarouselTemplate(
				columns=[
				CarouselColumn(
					title='類似したタイトルの本あるよ',
					text='検索したワードを含む本が見つかりました。気になるタイトルを選んでください',
					actions=actionslist
				)
				]
				)
	)
	return carousel_template_message
