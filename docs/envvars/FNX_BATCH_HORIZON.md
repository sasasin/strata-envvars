# `FNX_BATCH_HORIZON`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

sFNX の複数 lane 用 batched decoder が、新しい row layout の GPU graph capture コストを何個の window に配賦して評価するかを指定します。値が大きいほど capture コストの window あたりの見積もりが小さくなり、値が小さいほど大きくなります。これは row plan のコスト評価に使われる値で、window 数や生成長を制限する設定ではありません。根拠: `src/split/src/batch.cpp:64-85,287-310`、`src/split/src/batch_plan.hpp:127-148`。

## 値と判定

| 環境変数の状態 | 結果 |
|---|---|
| 未設定 | `4` |
| 整数 `1..1000` | その整数を horizon として採用 |
| 整数だが `1` 未満または `1000` 超 | `FNX_BATCH_HORIZON: 1 to 1000 windows` で例外 |
| 整数として不正 | `FNX_BATCH_HORIZON: '<値>' is not a whole number` で例外 |

`env_int` は base 10 の `strtoll` で文字列全体を読み、範囲外オーバーフローも不正値として扱います。任意の `+` / `-` 符号は受け付けますが、空文字、空白、数字以外の末尾、`long long` の範囲外は受け付けません。したがって `+4` は有効、`4x` や ` 4` は不正値、`0` や `-1` は整数 parse 後に範囲エラーです。根拠: `src/split/src/env.hpp:15-21,33-40`、`src/split/src/batch.cpp:81-83`。

## 有効になる条件

- `BatchDecoder` が構築される経路で読み取られます。通常の sFNX サーバーでは、batch slot が複数あり、`FNX_BATCH_DRAFTS` が `0`（off）でないときに decoder が作られます。`FNX_BATCH_DRAFTS` は未設定または `1` で MTP、`lookup` で lookup mode になり、`0` では off です（不正値は別の設定エラー）。根拠: `src/split/tools/sfnx.cpp:435-445`、`src/split/src/engine_common.cu:1020-1028`。
- `FNX_BATCH_FIXED` が `-1` のとき row plan が `choose_rows` で選ばれ、horizon が capture コスト評価に使われます。`FNX_BATCH_FIXED` が `0` 以上なら各 lane の draft 数を固定する分岐に入り、`choose_rows` を呼ばないため、この変数は plan に影響しません。根拠: `src/split/src/batch.cpp:77-80,287-310`。
- sFNX の起動時に作られた `BatchDecoder` の設定値です。値を読むのはコンストラクター内で、メンバー `horizon_` に保存されるため、そのインスタンスの稼働中にプロセス環境を変更しても再読込されません。CUDA/HIP や `FNX_27B` によって row cost の定数は異なりますが、horizon の範囲検査と capture 配賦式は共通です。根拠: `src/split/src/batch.cpp:64-85,287-300`、`src/split/src/batch.hpp:64-68`、`src/split/src/batch_plan.hpp:25-37`。

## 実行時の詳細

コンストラクターは `env_int("FNX_BATCH_HORIZON", 4)` で読み、範囲検査後 `double` に変換して `horizon_` に保存します。row plan が有効な `fixed_ < 0` の経路では `choose_rows(..., capture_ms_ / horizon_)` に値を渡します。プランナーは、まだ GPU graph が保持されていない layout の評価にこの capture 費用を加え、保持済み layout には capture 費用を加えず、期待 token 数 / 推定時間で候補を比べます。よって horizon は新しい layout の capture 費用の償却見積もりを変え、選ばれる row 配分に影響し得ます。根拠: `src/split/src/batch.cpp:287-310`、`src/split/src/batch_plan.hpp:127-191`。

capture 費用 `capture_ms_` の初期値は `10.0` ms ですが、Engine の `warm_capture_ms` が正ならその測定値に置き換えられます。また window 実行後に `last_capture_ms` が正なら、現在値と測定値の 80% / 20% の加重平均に更新されます。horizon 自体は固定のままです。根拠: `src/split/src/batch.hpp:64-65`、`src/split/src/batch.cpp:84-85,120-142`。

不正な文字列または範囲外整数では `BatchDecoder` 構築中に例外になります。sFNX は Server 構築時の例外を `fail(ex)` に渡し、stdout に `ERR <例外内容>`、stderr に `sfnx: failed: <例外内容>` を出して exit code 1 で終了します（`src/split/tools/sfnx.cpp:1063-1065,1027-1035,1091-1093`）。環境整数 parse の例外内容は `env.hpp` の文字列です。範囲エラーはそのまま `1 to 1000 windows` を含みます。CLI 引数による horizon の上書きはこの読み取り箇所にはありません。

## 根拠

- 読み取り、既定値、範囲検査、保存: `src/split/src/batch.cpp:64-85`
- 整数文字列の parse 規則: `src/split/src/env.hpp:15-21,33-40`
- horizon を使った row plan と固定 draft 分岐: `src/split/src/batch.cpp:287-310`
- capture 費用を含む候補評価: `src/split/src/batch_plan.hpp:127-191`
- sFNX server での decoder 構築条件: `src/split/tools/sfnx.cpp:435-445`
- `FNX_BATCH_DRAFTS` の値判定: `src/split/src/engine_common.cu:1020-1028`
