# `STRATA_PIPELINE_TRACE`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-15 調査、HEAD の commit 日 2026-10-14）。外部ライブラリの環境変数は対象外。

## 役割

`--pipeline-windows 2` の pipelined decode loop で発生するイベントと時刻を、指定ファイルへ追記する開発・診断用フックです。CUDA 系の `src/program/generate.cpp` と SYCL 実装の `sycl/src/program/generate.cpp` にあります。通常の decode 経路を選択したり、イベントの処理内容を変えたりする変数ではありません。

## 値と判定

値はファイル名として使われ、数値や真偽値には parse されません。`STRATA_PIPELINE_DEBUG` による共通 gate を通ったあと、pipelined decode loop の最初の実行時に `static const char*` として取得されます。

| `STRATA_PIPELINE_DEBUG` の状態 | `STRATA_PIPELINE_TRACE` の状態 | 結果 |
|---|---|---|
| unset、空文字、または先頭文字が `0` | 任意 | trace 変数は読み取り helper から `nullptr` を返され、記録しない |
| 設定され、先頭文字が NUL でも `0` でもない | unset | 出力先がなく、記録しない |
| 同上 | 空文字を含む任意の文字列 | その文字列を出力先パスとして使う。空文字では `fopen` が失敗するため出力されない |

`STRATA_PIPELINE_DEBUG` は文字列全体でなく先頭文字だけを判定します。空白や大文字小文字は検査せず、たとえば `false` や `2` は gate を有効にし、`0anything` は無効にします。trace のパス自体は変換・正規化されません。根拠: `src/program/generate.cpp:263-269`、`sycl/src/program/generate.cpp:295-300`。

## 有効になる条件

trace の値が有効でも、実際に記録するのは pipelined decode loop が実行された場合だけです。CUDA 系コードでは `pipe && pl_pw >= 2 && pl_snap_ok`、SYCL では `pipe && pl_pw >= 2 && pl_snap2[0] != nullptr` が要求され、さらにその request がキャンセルされておらず、生成上限にも達していない必要があります。適用されない request は通常の経路を使い、trace を追加しません。対応する分岐の前に、`penalty_last_n` による反復ペナルティまたは coupled draft sampling がある request は serial decode に回されます。

この変数と `STRATA_PIPELINE_*` のテスト・調整用変数は、`STRATA_PIPELINE_DEBUG=1` のような gate が有効なときだけ読まれると `docs/MULTI_GPU.md` にも記載されています。ただし実装上は値が厳密に `1` である必要はなく、前節の先頭文字判定です。根拠: `src/program/generate.cpp:11915-11926`、`sycl/src/program/generate.cpp:10639-10650`、`docs/MULTI_GPU.md:319-321`。

## 実行時の詳細

loop 開始時の `Clock::now()` から各イベントまでの経過時間をミリ秒で計算し、小数点以下3桁で `時刻 イベント名 seq x0 x1` の1行に整形してメモリ上の文字列に加えます。実装中のイベント名には `F0`、`CD`、`F1`、`U`、`CE`、`L0`、`L1`、`V`、`CL` があります。各イベントは loop 内の異なる進行点で記録されますが、5列の値自体に名前や凡例を付ける処理はありません。

loop の drain 後、イベントが1つ以上あれば出力ファイルを append mode (`"a"`) で開き、`# request p0=<n-1>` の区切り行とイベント行を追記して閉じます。したがって既存ファイルは上書きしません。ファイルを開けない場合のエラー表示や fallback はなく、書き込みの戻り値も確認しません。trace の文字列は request ごとに保持されます。

`STRATA_PIPELINE_DEBUG` の gate は helper 内の `static const bool` で初回評価時に固定されます。trace path も pipelined decode loop で初めて評価された値を static に保持するため、その後プロセス環境を変更しても再読込されません。根拠: `src/program/generate.cpp:266-269,12010-12020,12512-12528`、`sycl/src/program/generate.cpp:297-300,10759-10769,11271-11285`。

## 根拠

- 環境変数 gate: `src/program/generate.cpp:263-269`、`sycl/src/program/generate.cpp:295-300`。
- CUDA 系 loop の起動条件と記録バッファ: `src/program/generate.cpp:11915-11926,12010-12020`。
- SYCL loop の起動条件と記録バッファ: `sycl/src/program/generate.cpp:10639-10653,10759-10769`。
- 両 backend の追記処理: `src/program/generate.cpp:12512-12528`、`sycl/src/program/generate.cpp:11271-11285`。
- debug gate の文書上の説明: `docs/MULTI_GPU.md:319-321`。
