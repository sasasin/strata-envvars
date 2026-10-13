# `STRATA_EARLY_REMOTE_CONTEXTS`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリ・GPU ドライバー内部の挙動は対象外。

## 役割

`--expert-cache-device2` / `--expert-cache-device3` で使う補助 GPU の初期化時期を変えます。通常、CUDA1 の補助 GPU はモデルの CUDA0 重み領域を確保する前に初期化されますが、CUDA2/3 は CUDA0 の重み・MTP 用確保の後で初期化されます。この変数を有効にすると、設定された CUDA2/3 も CUDA1 と同じ早い段階で初期化します。補助 GPU のキャッシュ容量や割り当て内容を変える変数ではありません。

ソースコメントは、WSL2 で CUDA0 の重みと MTP がドライバーの pinned/mapped host budget（コメント上の目安は約 1 GiB）を先に使うと、後から CUDA2 などの context を作る処理が `out of memory` で失敗する場合がある、と理由を説明しています。これは実装コメントに記された背景であり、本調査で再現・測定した結果ではありません。

## 値と判定

`std::getenv()` で値を読み、設定されていて先頭文字が `1` の場合だけ有効です。文字列全体の parse はしません。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効（設定済みでも先頭文字は `\0`） |
| `1`, `10`, `1anything` | 有効 |
| `0`, `true`, ` 1`, `anything` | 無効 |

大文字小文字、数値としての妥当性、後続文字は検査されません。判定結果は `generate.cpp` の起動処理で一度ローカル変数に読み込まれ、その後は再評価されません。

根拠: `src/program/generate.cpp:2715-2720`。

## 有効になる条件

- `strata generate` の起動経路で、`--expert-cache-device2` または `--expert-cache-device3` に正のスロット数が設定されていること。指定のない GPU は早期初期化されません。
- レイヤー分割を使う場合は、補助 GPU 番号が「分割ステージで使わない可視 GPU」から割り当てられます。変数が有効でも、必要な可視 GPU がない場合は先行する引数・デバイス検査で終了します。
- `generate.cpp` のこの分岐自体に OS/backend 条件はありません。CUDA ビルドでは CUDA1〜3、レイヤー分割時は割り当て済みの補助デバイスに適用されます。`RemoteExperts::preflight()` 内の `cudaInitDevice()` は CUDA ビルドだけで呼ばれます。ただし `docs/SECOND_GPU.md:35-36` は補助 GPU 機能の条件を CUDA enabled build としています。文書でサポート対象とされるのは CUDA ビルドです。
- CUDA1（配列 index 0）の補助 GPU は、この変数が未設定または無効でも早期初期化されます。設定が影響するのは index 1/2（CUDA2/3相当）です。CUDA2/3 の補助キャッシュを使わない起動では、この変数による初期化順の差はありません。

根拠: `src/program/generate.cpp:2320-2329,2390-2404,2718-2724`、`src/core/remote_experts.cpp:68-89`。

## 実行時の詳細

判定箇所は、補助 GPU 番号を決めた後、CUDA0 の重み領域を割り当てる前にあります。ここで有効な各補助 GPU に `RemoteExperts::preflight()` を呼びます。同関数はデバイス数を確認し、CUDA ビルドでは `STRATA_REMOTE_SPIN` が未設定、または値の先頭文字が `0` 以外なら `cudaInitDevice()` を呼び、その後デバイスを切り替えて空きメモリを照会します。HIP ビルドでは `cudaInitDevice()` の呼び出しを行いません。成功時のログは `strata generate: CUDA%d context ready, %.2f GiB free before expert arena registration` です。

変数が無効なとき、index 1/2 の補助 GPU は CUDA0 の重み領域、セッション等の確保、および MTP の確保処理の後で初期化されます。位置はホスト expert arena の登録より前です。早期または後期の `preflight()` が失敗すると、stderr に `strata generate: ` とエラー内容を出し、終了コード 1 で処理を終えます。ソースにある失敗例には、可視デバイス範囲外とデバイス切り替え失敗があります。

したがって、この変数の効果は補助 GPU の初期化順に限られ、後期初期化に伴う失敗を必ず防ぐ保証や、追加の VRAM/host memory を確保する処理はありません。

根拠: `src/program/generate.cpp:2714-2729,2979-3010,4429-4454,4509-4519`、`src/core/remote_experts.cpp:68-89`。

## 文書との照合

`docs/SECOND_GPU.md:35-42` は補助 GPU、host arena の登録上限、および CUDA0 の文脈を説明していますが、この環境変数による CUDA2/3 の初期化時期は記載していません。`docs/DETAILS.md` にも変数名の説明は見つかりませんでした。挙動と値の判定は上記 HEAD の実装を根拠にしています。
