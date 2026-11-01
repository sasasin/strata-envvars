# `STRATA_VERIFY_TRACE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の Strata 作業ツリーは `## main...origin/main` で、未コミット変更はありません。

## 役割

Verifier の診断用 trace を有効にします。有効時、ホスト側では verifier の handshake event をリングバッファへ記録し、GPU 側では layer/token group ごとの profiler stamp（breadcrumb）を mapped memory に記録します。これは診断情報の記録・表示を切り替えるもので、生成や検証の計算結果を選ぶ設定ではありません。

Strata 所有の本番コードでの読み取りは CUDA/HIP 共通の `src/core/verify.cpp` と SYCL 実装 `sycl/src/core/verify.cpp` に各1箇所あります。両方とも同じ `env_on()` 判定を使います。候補一覧にある名前は実際に読み取られており、誤検出ではありません。

## 値と判定

| 環境値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効 |
| 先頭文字が `0`（例: `0`, `0abc`） | 無効 |
| それ以外の非空文字列（例: `1`, `true`, `false`, ` 0`） | 有効 |

文字列全体の比較や数値変換はしません。先頭文字だけを検査し、大文字小文字や後続文字は無視します。そのため `false` も有効です。既定は無効です。CLI 引数や別の環境変数による上書きはありません。値は各実装のファイルスコープ `const bool g_trace` の初期化時に一度判定されるため、その後にプロセス内で環境値を変えても反映されません。

根拠: `src/core/verify.cpp:299-307`, `sycl/src/core/verify.cpp:94-102`。

## 有効になる条件

Verifier のコードを含む実行ファイルで有効です。CUDA/HIP では `src/core/verify.cpp`、SYCL では同じ処理を移植した `sycl/src/core/verify.cpp` が使われます。OS、GPU 世代、サーバーモード、モデル形式による値判定の違いはありません。ただし診断情報が作られるのは Verifier が実際に初期化・実行される経路です。Verifier を使わない通常処理には trace 出力はありません。

`Verifier::init()` は有効時に GPU breadcrumb 用 mapped memory の割り当てを試みます。割り当てに失敗すると breadcrumb 領域を null に戻しますが、trace の設定自体は無効化せず、初期化ログも出します。この場合もホスト event ring は `g_trace` により記録されますが、GPU breadcrumb の表示はできません。割り当て成功は trace を有効にする条件ではありません。

根拠: `src/core/verify.cpp:1005-1020`, `sycl/src/core/verify.cpp:622-636`。

## 実行時の詳細

`trace_ev()` は有効時に event の時刻、Verifier、window/step/layer、補助値、handshake word を最大4096件のグローバル ring に記録します。window の開始、launch、GPU の応答、CPU serve、timeout、release などが記録対象です。dump はそのうち直近最大160件を出し、GPU breadcrumb 領域がある場合は GPU が到達した layer 付近の stamp も表示します。領域に stamp がなければ `strata verify trace: no GPU breadcrumb in this window (the GPU never started it)` と出します。

有効化時、Verifier 初期化で stderr に `strata verify trace (#649): on` を出します。HIP ビルドでは同じ行に coherent words / doorbell の状態と `HIP_HOST_COHERENT`、`HSA_ENABLE_SDMA`、`GPU_MAX_HW_QUEUES` の値も表示します。後者3つはこの trace のログ表示に使われるだけで、`STRATA_VERIFY_TRACE` の判定条件ではありません。この文書はそれら外部側の意味を扱いません。

trace dump は通常の成功ごとに出るものではありません。たとえば CUDA/HIP と SYCL の通常 window では layer wait が timeout した際に、Verifier の状態と trace を stderr に出し、GPU wait を最大5秒 drain してから `verify: timed out at layer N` の失敗を返します。適応層 gate の20秒 timeout でも `GATE-TIMEOUT` event と dump を出し、tier のコピー未到着エラーを返します。layer が GPU から応答しない `NEVER-RANG` 経路も dump を試みますが、trace が無効なら `trace_dump()` は何も出しません。timeout の時間や失敗判定そのものをこの変数は変更しません。

サーバーの watchdog は engine log の直近256 KiBを読み、その中から issue #29 の行を探します。ソースコメントによれば trace dump は約30 KiBで、従来の4 KiB tail より前に watchdog 行を押し出すことがあるため、server は広い範囲を走査します。これは環境変数の判定ではなく、trace を含むログを扱うサーバー側の処理です。

根拠: `src/core/verify.cpp:557-559,614-670,673-682,1005-1020,2976-2991,3213-3235`; `sycl/src/core/verify.cpp:298-300,345-401,404-413,622-636,2338-2368`; `serve/server.py:1264-1280`。

## 根拠

- 値判定と読み取り箇所: `src/core/verify.cpp:299-307`, `sycl/src/core/verify.cpp:94-102`。
- trace event の保存と dump 内容: `src/core/verify.cpp:549-559,614-670`; SYCL 側 `sycl/src/core/verify.cpp:290-300,345-401`。
- mapped breadcrumb の確保と有効時ログ: `src/core/verify.cpp:1005-1020`; SYCL 側 `sycl/src/core/verify.cpp:622-636`。
- timeout と失敗経路: `src/core/verify.cpp:2976-2991,3213-3235`; SYCL 側 `sycl/src/core/verify.cpp:2338-2368`。
- server log の検索範囲: `serve/server.py:1264-1280`。
