# `STRATA_VERIFY_TRACE`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

Verifier の診断用トレースを有効にする。ホスト側では window の開始・GPU launch・layer 到達・CPU 側の serve・timeout・GPU wait の解放などをイベント ring に記録する。GPU 側では verifier の計算区間ごとの到達時刻を mapped memory に記録する。モデル計算の選択や結果を制御する設定ではなく、記録領域を追加して診断情報を出すためのフックである。

CUDA/HIP 実装と SYCL 実装の両方に読み取り箇所がある。通常推論での利用を前提とした一般設定というより、Verifier の停止・timeout を調べる診断用 opt-in である。

## 値と判定

`env_on()` は `getenv()` の結果が null でなく、かつ先頭文字が NUL と `'0'` のどちらでもない場合に true を返す。文字列全体の parse や数値変換はしない。

| 値 | 判定 |
|---|---|
| 未設定 | OFF |
| 空文字 | OFF |
| `0` または `0anything` | OFF |
| `1`、`2`、`true`、`false`、空白で始まる文字列など | ON |

大文字小文字や後続文字は判定されない。したがって `false` も ON である。グローバル定数 `g_trace` の初期化時に一度読み取られ、そのプロセス内では後から環境を書き換えても変化しない。

根拠: `src/core/verify.cpp:172-180`、`sycl/src/core/verify.cpp:92-100`。

## 有効になる条件

- Verifier が使われる CUDA/HIP または SYCL の実行経路で有効。ビルド内で対応する `verify.cpp` が使われない経路には影響しない。
- 値が ON でも Verifier が初期化・実行されなければイベントは発生せず、出力もない。
- GPU breadcrumb 用の mapped allocation に失敗した場合、実装はその pointer と要素数を null/0 に戻す。ホスト側イベント記録は `g_trace` を見て独立に行われるため、trace dump 自体は可能だが GPU breadcrumb 部分は出ない。
- OFF の場合、trace event の記録と trace dump は早期 return する。通常の verifier の待機・timeout 判定はこの環境変数で変更されない。

## 実行時の詳細

`Verifier::init()` は有効時に、layer 数に応じた `(n_layers + 1) * kProfPer * 2` 個の GPU breadcrumb を mapped memory に確保しようとする。各 window の開始時に領域をゼロクリアし、GPU 計算の区間ごとに stamp を書く。CUDA/HIP では stamp の記録箇所が `src/core/verify.cpp:847-848`、SYCL では `sycl/src/core/verify.cpp:830-833` にある。

ホストイベントは verifier 全体で共有する 4096 件の ring に追加される。dump はそのうち最新 160 件までを表示し、各イベントのホスト時刻、window、step、layer、補助値、seq/flag/A/B の値を出す。breadcrumb が存在すれば、GPU が進んだ layer 近傍の区間別時刻も表示する。GPU が window を開始していない場合は `strata verify trace: no GPU breadcrumb in this window (the GPU never started it)` と表示する。

各 Verifier の初期化時、breadcrumb 領域が未確保なら stderr に `strata verify trace (#649): on` を出す。HIP ビルドでは同じ行に coherent words / doorbell の状態と `HIP_HOST_COHERENT`、`HSA_ENABLE_SDMA`、`GPU_MAX_HW_QUEUES` の現在値も出す。これらの外部変数の意味はここでは扱わない。

trace dump は、通常の watchdog 診断 (`diag()`)、GPU が layer に到達しないと判定されたとき、または verifier の timeout 時に呼ばれる。timeout 時に有効なら、wait 解放前に `diag(stderr)`、解放後に再度 dump して、解放後に GPU が進んだかを記録する。timeout 自体の判定・解放処理は無効時も実行される。

根拠: `src/core/verify.cpp:355-365,407-464,466-475,694-709,847-848,2163-2174,2210-2228`、`sycl/src/core/verify.cpp:296-306,351-408,410-419,620-634,830-833,2023-2030,2220-2248`。

## 根拠

- `src/core/verify.cpp:172-180` — 環境変数の判定と `g_trace` の初期化。
- `sycl/src/core/verify.cpp:92-100` — SYCL 側にも同じ判定がある。
- `include/strata/core/verify.hpp:88-90,422-428`、`sycl/include/strata/core/verify.hpp:70-72,370-376` — opt-in 診断としての宣言、mapped breadcrumb 領域と stamp 数。
- `src/core/verify.cpp:414-464`、`sycl/src/core/verify.cpp:358-408` — host event と GPU breadcrumb の dump 内容。
- `src/core/verify.cpp:694-709,847-848`、`sycl/src/core/verify.cpp:620-634,830-833` — 診断領域の確保、開始ログ、GPU stamp。
- `src/core/verify.cpp:2210-2228`、`sycl/src/core/verify.cpp:2220-2248` — 到達失敗・timeout 時の dump。

`docs/DETAILS.md` および他の設計資料に、この環境変数の利用者向け説明や測定値は見つからなかった。根拠は上記実装とヘッダーの記述に限る。
