# `STRATA_MTP_SIDE_STREAM`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

HIP 版の MTP drafter 初期化時に、非同期 side stream を作成するか指定します。現行 HIP 実装では共有 expert の処理を side stream に分岐せず、`cs_` 上で実行します。そのため、この環境変数が直接変えるのは `MtpDrafter::load()` が `side_` を作成するかどうかです。CUDA 版は共有 expert 用 side stream とイベントを常に作成し、この環境変数を読みません。

MTP drafter 自体が作られるのは `strata generate` に `--mtp` があり、`--spec` が 2 以上の場合です。`--batch-mtp` では slot ごとの drafter も作られ、それぞれの `load()` で設定を判定します。

## 値と判定

| 状態 | HIP (`STRATA_USE_HIP`) の結果 |
|---|---|
| 未設定 | 現在の GPU 名が `gfx103` で始まる場合に作成。それ以外は作成しない |
| 空文字 | GPU 名による既定値を維持 |
| 空でない値 | `std::atoi(value) != 0` なら作成、0 なら作成しない |

文字列全体の妥当性は検査しません。`atoi` の10進数変換なので、たとえば `1junk` や先頭空白のある ` 1` は 1 と判定され、`junk` や `0junk` は 0 と判定されます。大文字小文字による判定はありません。空文字だけは `atoi` に渡さず、既定値を保ちます。

`STRATA_USE_HIP` 以外のビルドではこの名前を読む箇所がありません。通常の CUDA 経路は side stream と関連イベントを常に作成します。SYCL の MTP 実装にもこの変数の読み取りはありません。

根拠: `src/core/mtp.cpp:434-459`、SYCL 側の対応する初期化 `sycl/src/core/mtp.cpp:420-465`。

## 有効になる条件

- HIP 版では `MtpDrafter::load()` がストリーム初期化まで成功することが必要です。`side_` の作成が失敗すると `load()` は `err = "mtp: streams"` を設定して失敗します。
- 既定で作成される GPU は、`cudaGetDevice()` と `cudaGetDeviceProperties()` が成功し、`prop.gcnArchName` の先頭6文字が `gfx103` の場合です。GPU 情報の取得に失敗した場合の既定値は off です。
- 明示値はこのアーキテクチャ既定値を上書きします。HIP の gfx103x でも `0` 相当値で無効にでき、他の HIP GPU でも非ゼロ値で作成できます。
- `--mtp` がなければ該当 drafter の `load()` が呼ばれず、環境変数の判定も行われません。

## 実行時の詳細

判定は `MtpDrafter::load()` ごとに行われ、関数内の static cache ではありません。値はストリーム作成時にのみ参照されるため、作成後にプロセス環境を書き換えても、その drafter の `side_` は変わりません。作成した `side_` は `MtpDrafter` のデストラクタで破棄されます。

HIP の `record_forward()` では `branch_on` がコンパイル時に `false` となり、共有 expert は `cs` 上で実行されます（`src/core/mtp.cpp:885-894,895-941`）。従って `STRATA_MTP_SIDE_STREAM` が HIP で `side_` を作成しても、Strata のこのコードは共有 expert の処理をその stream に投入しません。実装コメントと `docs/AMD_HIP.md` は gfx103x で stream の存在により prompt の「wait copy」時間が短くなった測定を記録していますが、その効果の内部原因は Strata ソースからは確認できません。

CUDA では `side_` と `sh_fork_` / `sh_join_` を無条件に作成し、`STRATA_MTP_SHARED_BRANCH` の既定・値判定を使って共有 expert を分岐実行する別の制御があります。この経路に `STRATA_MTP_SIDE_STREAM` は関与しません（`src/core/mtp.cpp:434-440,885-941`）。

## ログと測定値

ストリーム作成失敗時の呼び出し元ログは、通常の drafter なら `strata generate: mtp: streams` の形式です。成功時に side stream の有効・無効だけを示すログはありません。

`docs/AMD_HIP.md:219-225` は次の HIP 測定を記載しています。RX 6800 / Windows / `STRATA_HIP_PROMPT_F16=1` / IQ3_XXS で、7.9K-token prompt は side stream あり 798–808 tok/s、なし 584–596 tok/s、30.4K-token prompt はあり 855–863 tok/s、なし 553–600 tok/s。文書は `STRATA_PREFILL_TIMING=1` の「wait copy」がそれぞれ 3,081→75 ms、12,642→288 ms と記録し、decode と出力は同じだったとしています。これは記載された単一カード・単一 OS の測定で、他環境での性能を保証しません。同資料は gfx103x では `STRATA_MTP_SIDE_STREAM=0` で無効化し、他の HIP GPU では `=1` で作成できるとしています。

## 根拠

- `src/core/mtp.cpp:423-459` — stream 初期化、HIP のアーキテクチャ既定値、環境値の変換、作成エラー。
- `src/core/mtp.cpp:130-162` — 作成された stream とイベントの破棄。
- `src/core/mtp.cpp:885-941` — HIP では共有 expert を `cs` 上で実行し、CUDA では分岐 stream を使う条件。
- `src/program/generate.cpp:4480-4514` — `--mtp` での drafter 読み込みと batch slot drafter の作成。
- `sycl/src/core/mtp.cpp:420-465` — SYCL 側にこの環境変数の読み取りがないことを照合。
- `docs/AMD_HIP.md:219-225` — HIP の用途説明と測定条件・値。
