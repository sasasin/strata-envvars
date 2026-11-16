# `STRATA_FEED_MODELS`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

Control のモデルカタログに、署名済み update feed の `models` 一覧を読み込み、オフライン用キャッシュも含めて追加する処理を停止するためのスイッチです。`STRATA_FEED_MODELS` を空白除去後に `0` とすると、一覧の読み込み・取得を止めます。モデル一覧の登録は `setup.py` の setup メニュー、アプリと Terminal のカタログで共有されます。エンジンの推論処理を切り替える変数ではありません。`strata_control/feed_models.py:110-115`、`setup.py:8568-8582`、`tools/strata_mcp.py:550-576`。

update feed 全体の取得や更新を無効化するものではありません。`strata update` などが feed を読む `updater.open_feed()` はこの変数を参照せず、取得済み feed の `models` をキャッシュへ保存します。その後のモデル一覧読込がこの変数で止められます。`strata_control/updater.py:433-452`。

## 値と判定

`feed_models.load()` は `os.environ.get(ENV_OFF, "").strip() == "0"` を評価します。変換は空白除去だけで、数値 parse や真偽値変換はしません。前後の Unicode 空白を除いて文字列全体が `0` と一致する場合だけ停止します。大文字小文字の区別が問題になる値比較ではなく、`true` 等を認識する仕組みもありません。未設定、空文字、および `0` 以外の値は停止条件になりません。`strata_control/feed_models.py:32-34,110-115`。

| 条件 | 未設定 | 停止する値 | 停止しない値の例 |
|---|---|---|---|
| 全ての Control 読み込み経路 | `get(..., "")` により空文字となり、通常の読込経路へ進む | `0`、` 0 `（前後空白を除去して厳密一致） | 空文字、`00`、`0anything`、`1`、`true`、`false`、` 1 ` |

停止条件に一致すると `Loaded()` を直ちに返すため、その呼び出しでは署名鍵の読込、キャッシュ確認、ネットワーク取得を行いません。feed 由来モデルはその呼び出しで setup の表へ追加されません。`strata_control/feed_models.py:110-115`。

## 有効になる条件

- `strata_control.feed_models.load()` が呼ばれたときに評価されます。環境変数が設定されていても、同関数が呼ばれない処理には影響しません。`strata_control/feed_models.py:110-115`。
- setup の通常メニューは、family と `--yes` が指定されていない場合に一覧を読み込みます。未知の `--family` または `--model` を指定した setup 経路も、既知の名前か判定する前に一覧を読み込みます。`setup.py:9339-9344,9857-9861`。
- アプリ／Terminal のカタログは `tools/strata_mcp.py` が setup.py を初回ロードするとき `feed_models_setup(fetch=False)` を呼び、キャッシュだけを読みます。`STRATA_FEED_MODELS=0` の場合はこのキャッシュ読込も止まります。`tools/strata_mcp.py:550-576`、`setup.py:8568-8582`。
- setup がネットワークから一覧を得るのは `fetch=True` かつ acquisition が禁止されていない場合に feed source を決定できたときです。`--feed` はこの取得元選択に渡されます。取得できない場合は `load()` が最後に検証されたキャッシュを使いますが、環境変数が停止値ならキャッシュへの fallback も行いません。`setup.py:8572-8582`、`strata_control/feed_models.py:123-137`。
- 有効な一覧が読み込まれた場合も、署名鍵がない・読み込めない、cache/feed の検証ができない場合はモデル一覧が返らないことがあります。feed の取得失敗はログに記録して、検証済み cache があればそれへ fallback します。`strata_control/feed_models.py:117-137`。
- OS、GPU backend、build macro、サーバーモードによる値判定の違いはありません。この処理は Control の Python コードにあります。モデル登録後の可用性は別途、現在の engine family 等で決まります。`strata_control/feed_models.py:204-248`。

## 実行時の詳細

環境変数は `load()` の各呼び出し時に読みます。関数内 static cache はなく、Python プロセスで呼び出し間に `os.environ` を変更すれば次の呼び出しの判定に反映されます。ただし、アプリ／Terminal の `Strata.setup_module()` はインスタンスごとに一度だけ setup.py を読み込み、その際に cache-only の一覧読込を行います。モジュール表を初期化した後の環境変更だけで、その表が再読込されるわけではありません。`strata_control/feed_models.py:110-115`、`tools/strata_mcp.py:542-576`。

停止値でない場合、`load()` は信頼鍵を読み、キャッシュ済み feed の署名を再検証します。source があり fetch が有効なら feed を取得し、取得に成功すると `remember()` で署名付き feed 文書を保存してそのモデル一覧を返します。取得失敗時は有効なキャッシュ一覧へ fallback し、どちらも使えなければ空の `Loaded` を返します。`strata_control/feed_models.py:87-98,110-137`。

キャッシュ書込みはこの変数の gate の外にもあります。`strata_control/updater.py:433-452` の通常 update/check feed 読込は `feed_models.remember()` を呼びます。従って停止値は cache の読込・一覧反映を抑止しますが、update/check 自体や feed の取得、cache への書込み・撤回を止めません。cache は `<components>/.updates/feed-models.json` に置かれます。`strata_control/feed_models.py:55-58,61-84`。

## ログと測定値

停止値に一致した `load()` は空結果を返すだけで、この分岐自体はログを出しません。停止値でない経路では、feed 取得の失敗時に logger `strata.feed` へ `the update feed's model list could not be refreshed: %s` を info レベルで記録します。キャッシュ保存に失敗すると `the model list of the update feed could not be kept for offline use: %s` を warning レベルで記録します。`strata_control/feed_models.py:83-84,128-131`。

設定値による性能・正確性の測定値はありません。

## 根拠

- `strata_control/feed_models.py:32-34,110-137` — 環境変数名、判定、読込・cache fallback。
- `strata_control/feed_models.py:55-84,204-248` — cache の場所・保存、feed モデルの表への登録。
- `setup.py:8568-8582,9339-9344,9857-9861` — setup の読込入口と実行条件。
- `tools/strata_mcp.py:542-576` — アプリ／Terminal カタログの初回 cache-only 読込。
- `strata_control/updater.py:433-452` — 独立した update feed 読込と cache 保存。
