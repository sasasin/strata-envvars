# `STRATA_METAL_STREAM_FAKE`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。Strata 所有のソースを対象とし、外部ライブラリの動作は含めない。

## 役割

Metal engine の expert streaming 経路で、arena にない expert の読み込みを省いて計測するための診断用フックです。設定を有効にすると、欠けている expert の参照先を slot 0 に向け、実際の読み込みをせず `at_layer()` から戻ります。ソースのコメントも「timing only (WRONG answers)」と明記しており、このモードの推論結果は正しくありません。

この変数は `ExpertStream::open()` でのみ読まれ、そのインスタンスの `fake_` に保存されます。`Window::init()` は streaming を選んだ場合だけ `ExpertStream` を生成・open します。そのため、streaming が選ばれない実行では変数は読まれず、効果もありません。

## 値と判定

共通 helper `env_int()` は、変数が未設定または空文字なら既定値を返し、それ以外は `std::atoi()` の結果を返します。この変数の既定値は `0` で、結果が非ゼロなら fake mode が有効です。

| 値の状態 | `atoi` / helper の結果 | fake mode |
|---|---:|---|
| 未設定 | 既定値 `0` | 無効 |
| 空文字 | 既定値 `0` | 無効 |
| `0`、`00`、`-0` | `0` | 無効 |
| `1`、`-1`、`2tail` | それぞれ `1`、`-1`、`2` | 有効 |
| 数字で始まらない文字列（例: `true`, `junk`） | `0` | 無効 |

数値全体との一致検査ではありません。`atoi` が先頭の空白と符号を許し、数字列の後ろを変換対象にしないため、たとえば ` 1x` は有効になります。数値変換の範囲外入力に対する `atoi` の結果は、この実装で保証されません。

## 有効になる条件

- `metal/src/engine/window.cpp` の `Window::init()` で `ExpertStream::wanted()` が true となり、`st_->open()` が成功している必要があります。streaming は `STRATA_METAL_STREAM=1` で明示的に選ばれるか、同変数が未設定または `0` 以外の自動判定値で、GGUF の expert 重量が Metal GPU の resident footprint に収まらない場合に選ばれます。`STRATA_METAL_STREAM=0` は streaming を使わない経路です。
- `ExpertStream::at_layer()` が層ごとに呼ばれる必要があります。通常の `Window` 経路は `at_cut()` からこれを呼び出します。
- 既に arena にある expert には fake 処理を行いません。`where_` が負値である（arena にない）要求 expert だけ `smap_` 上の値を `code_[0]` に置き換えます。

対象コードは Metal engine のみです。別 backend や外部 Metal/driver の環境変数解釈を示すものではありません。

## 実行時の詳細

`ExpertStream::open()` が `STRATA_METAL_STREAM_FAKE` を `atoi` で評価して `fake_` に保存します。`Window::init()` は streaming 経路で `ExpertStream` を開き、その後 `at_cut()` が各層の token ごとの expert ID を `at_layer()` に渡します。

fake mode では、要求された expert ID ごとに arena 未配置かを確認し、未配置なら `smap_[layer * 512 + expert]` に `code_[0]` を設定します。その後、通常の slot 割当て、I/O queue への submit、読み込み完了待ちは行わずに戻ります。従って、未配置 expert の実データは読み込まれず、参照先が slot 0 に集約されます。これは実際の生成に使う設定ではなく、streaming の時間計測で誤答を許容する場合のみに限られる動作です。

この変数自体によるログ、警告、エラー出力は見つかりませんでした。`atoi` を呼ぶ `open()` のたびに評価されるため、open 前に設定を変えればそのインスタンスの値に反映されますが、open 後に環境を書き換えても既に保存された `fake_` は変わりません。

## 根拠

- `metal/src/engine/stream.cpp:27-30`: `env_int()` の未設定・空文字の既定値と `atoi` 変換。
- `metal/src/engine/stream.cpp:149-163`: `STRATA_METAL_STREAM_FAKE` の既定値、非ゼロ判定、診断用コメント。
- `metal/src/engine/stream.cpp:614-633`: 要求 expert ID の収集、arena miss だけ `code_[0]` を使う処理、fake mode の早期 return。
- `metal/src/engine/window.cpp:292-295,409-435`: streaming 時の層 callback と `ExpertStream` の生成・open 条件。
- `metal/src/engine/stream.h:37-40,102-109,119-120`: streaming の選択説明、slot mapping と `fake_` のメンバー。
- `metal/setup_mac.py:670-675`: setup が `STRATA_METAL_STREAM` を起動設定へ書く箇所。
