# `DS4_STORE_SPARE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

DeepSeek V4.1 の RAM store がモデル起動時に先読みする expert の候補に、GPU の VRAM cache にある低利用頻度 expert と、利用履歴のない CPU 側 expert も加えるかを選びます。有効時は store の空き容量を予約枠として残さず、この追加候補にも使います。値は RAM store 自体を有効にする設定ではありません。

## 値と判定

Strata は `env_tri()` で `getenv()` の値を `atoi()` に渡し、変換結果が 0 なら明示的な OFF、0 以外なら明示的な ON、未設定なら `-1` とします。`store_feature_default()` は明示値を `DS4_DEFAULTS` の値より優先し、未設定の場合だけ既定値を使います。

| `DS4_STORE_SPARE` | 判定 |
|---|---|
| 未設定 | `DS4_DEFAULTS` が `026`、`0.2.6`、`v0.2.6` のいずれかなら OFF。それ以外は ON（`DS4_DEFAULTS` も未設定なら ON） |
| `0`、空文字、数値に変換できない文字列（例: `false`） | OFF。`atoi()` の結果が 0 |
| `1`、`2`、`-1` など、`atoi()` の結果が 0 以外 | ON |

これは文字列全体の真偽値 parse ではありません。`atoi()` が読む先頭の整数部分で決まり、たとえば `1tail` は ON、`0tail` は OFF、先頭に空白がある ` 1` は ON です。範囲外の数値を含む入力の `atoi()` の結果は保証されないため、その値での挙動は定められません。

明示的な値は `DS4_DEFAULTS` を上書きします。DeepSeek 向けの CLI に `DS4_STORE_SPARE` 専用引数はありません。アプリと Terminal の「DeepSeek speed-ups」を既定の ON から OFF にすると、起動環境へ `DS4_STORE_SPARE=0`（現行設定では他の DeepSeek 変数と併せて `DS4_DEFAULTS=026` も）を設定します。

## 有効になる条件

この変数が効果を持つのは、DeepSeek V4.1 モデルの初期化で RAM store が作成され、expert profile に利用履歴がある場合です。store は容量が正で、レイヤーの形式が MXFP4 で、file expert が存在するときに初期化されます。容量には `--ssd-cache` または `DS4_STORE_GB` が関係し、環境変数 `DS4_STORE_GB` は CLI の `--ssd-cache` より優先されます。自動容量が選ばれる場合は、利用可能 RAM 等に応じて 0 となり store が作られないこともあります。store の初期化に失敗した場合も先読みは行われません。

profile の全 expert の利用数が 0 以下なら、先読み関数は環境変数を判定する前に戻ります。従って、設定が ON でも store や履歴がない起動ではこの機能は動作しません。OS / CUDA・HIP・Metal の個別条件による `DS4_STORE_SPARE` の分岐は見つかりませんでした。

## 実行時の詳細

モデル初期化は `init_store()` の後に `preload_store()` を呼びます。先読み対象の基礎リストは、VRAM にない expert のうち profile の利用率が高いものを利用率/サイズ順で並べたものです。機能が ON なら、VRAM にある expert を利用率/サイズの低い順に追加し、さらに profile に記録がない CPU 側 expert を加えます。これらは候補リストの後方なので、容量に余裕がある場合に先読みされます。

ON の場合、先読み時に残す枠数 `leave` は 0 です。OFF の場合は `DS4_STORE_RESERVE` が設定されていればその `atoi()` 値、未設定なら 192 を使い、さらに 64 を加えます。`ExpertStore::preload()` は最大枠数から `leave` を引いた数までをリスト順（先読み内部では冷たい順から slot を割り当て）に読み込みます。別の `DS4_STORE_BG=1` は先読みリストを分割し、先頭を同期、残りをバックグラウンドで読む指定です。ON/OFF の候補選定と予約枠の違いは変わりません。

`env_tri("DS4_STORE_SPARE")` 自体は `static` cache されず、`preload_store()` の候補選定と予約枠計算でそれぞれ読みます。一方、未設定時に参照する `DS4_DEFAULTS` は `defaults_026()` 内の `static const` に初回評価結果が保存されます。どちらも通常のモデル初期化中に判定され、以降のリクエストごとの切り替えではありません。

変数専用の警告・エラーや有効状態を示すログはありません。store が開始できない場合は stderr に `ds4: --ssd-cache: the store could not start`、成功時には RAM store の容量・policy・reader 数を示す一般ログが出ます。profile 付きで先読みすると `ds4: RAM store: ... experts read in ...`、バックグラウンド分がある場合は完了後に追加ログが出ます。実行統計では store のヒット・ミス、読み込み量、slot 数などを確認できますが、`DS4_STORE_SPARE` の値そのものは表示されません。

## 根拠

- `src/dsv41/ds4_model.cu:97-101` — `env_tri()` の未設定と `atoi()` による 0/1 化。
- `src/dsv41/ds4_experts_rule.hpp:203-208` — 明示値を優先し、未設定なら 0.2.6 相当では OFF、それ以外では ON とする規則。
- `src/dsv41/ds4_experts_rule.hpp:22-27` — `DS4_DEFAULTS` の完全一致 token と static cache。
- `src/dsv41/ds4_model.cu:3183-3185,5410-5418,5487-5500,5525-5537` — model init からの呼び出し、store の成立条件、store 起動ログ、profile がない場合の早期 return。
- `src/dsv41/ds4_model.cu:5544-5583` — 追加される候補、予約枠、先読みとバックグラウンド分割。
- `src/dsv41/ds4_store.hpp:221-239` — `preload()` が空き枠から予約分を差し引き、候補を読み込む処理。
- `src/dsv41/ds4_main.cpp:1589-1601` — store がある場合に出す一般的な実行統計。
- `strata_control/speed_switches.py:48-55`, `apps/host/server/native-settings.mjs:49-53` — DeepSeek speed-ups の設定で `DS4_STORE_SPARE=0` を渡す構成。
