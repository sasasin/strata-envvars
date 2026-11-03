# `STRATA_LOOKUP_MAX_T`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

この変数は prompt-lookup の長い verify window を直接指定するものではなく、`--lookup-max-t` が省略されたときの既定値 12 を抑止するために使われます。値の先頭文字が `0` なら既定値候補を 0（無効）にします。それ以外の値で既定機能を有効化するわけではなく、有効条件を満たす場合に限り既定値 12 が選ばれます。根拠: `src/program/generate.cpp:4140-4155`、`include/strata/core/lookup_default.hpp:9-27`。

機能が有効な serve 実行では、suffix drafter が過去の prompt の一致箇所から提案する window を MTP の `--spec` window より長くでき、上限は `--lookup-max-t`（既定値の場合 12）です。許可された各 window サイズは専用の CUDA graph として準備され、VRAM に収まらないサイズは候補から外して小さいサイズへ進みます。根拠: `src/program/generate.cpp:1300-1319,13417-13437,18233-18250`、`include/strata/kernels/verify_kernels.hpp:23-31`。

## 値と判定

環境変数は `std::getenv()` で読み、文字列全体の parse はせず `lme[0] == '0'` だけを判定します。空白・大文字小文字・数値としての妥当性・後続文字は検査しません。

| 環境値 | `env_off` | 既定値への影響 |
|---|---:|---|
| 未設定 | false | 他の条件を満たせば 12 |
| 空文字 | false | 他の条件を満たせば 12 |
| `0`, `00`, `0anything`, `0.5` | true | 自動既定値は 0（無効） |
| ` 0`, `.5` | false | 先頭が `0` ではないため、他の条件を満たせば 12 |
| `1`, `12`, `true`, `false`, その他 `0` 以外で始まる文字列 | false | 他の条件を満たせば 12。値自体は上限値として使われない |

読み取りは `o.lookup_max_t < 0` の場合だけ行われます。`Options` の初期値は `-1` で、CLI の `--lookup-max-t N` は `std::atoi()` で変換して `std::max(0, ...)` した値を設定するため、明示した CLI 値が環境変数の判定より優先します。CLI に不正な数値文字列を渡すと `atoi()` の結果 0 となり、負値も 0 に clamp されます。根拠: `src/program/generate.cpp:972-977,3551,4143-4155`。

## 有効になる条件

環境変数が未設定または先頭文字が `0` 以外でも、コード上の自動既定値が 12 になるのは次の条件をすべて満たす場合だけです。

- build の verify 窓が narrow（`kVerifyMaxT == kVerifyNarrowT`。narrow は 8 行）。CUDA/HIP の窓上限はビルド設定から決まり、Metal/SYCL は共通 header の既定 8 行です。
- `--serve` を使い、単一 GPU である。layer split、`--batch`（batch 数が 1 より大きい）、DFlash2 draft、`--lookup-chain` は使わない。
- suffix draft が有効（`--suffix-draft > 0`）で、`--spec >= 2`。
- Metal build ではない。

これらの条件のいずれかを満たさない場合、自動既定値は 0 です。特に、非 serve の起動では環境変数で既定機能を有効にしません。`--lookup-max-t` を明示すれば、上記の環境変数による自動既定値判定を通らず、指定値が使われます（ただし後段の serve 経路や backend の制約は別に適用されます）。根拠: `include/strata/core/lookup_default.hpp:23-27`、`include/strata/kernels/window_limits.hpp:3-25`、`src/program/generate.cpp:4143-4158`。

## 実行時の詳細

変数はオプション処理後の設定構築時に一度読み取られ、`LookupDefaultIn` に `env_off` と他の実行条件を渡して自動値を決めます。static cache はなく、serve の各要求で読み直す実装でもありません。プロセス起動後の環境変更は、既に決定された `o.lookup_max_t` に反映されません。Strata がこの変数を子プロセスへ転送・上書きする箇所は候補名の全参照検索では見つかりません。参照: `src/program/generate.cpp:4143-4155`。

値が正なら serve の draft policy に lookup window サイズを設定し、開始時に stderr へ `strata serve: --lookup-max-t ...` の設定ログを出します。サイズごとの graph 準備で VRAM が不足した場合、そのサイズを policy から除き stderr に `no VRAM for the ...-token window graph` と残りサイズを表示し、小さいサイズで試します。VRAM 不足以外の graph 準備失敗はこの fallback ではなく、呼び出し側のエラー経路に進みます。根拠: `src/program/generate.cpp:13417-13437,18237-18250`。

値の判定だけでは別の成功ログや警告は出ません。`STRATA_LOOKUP_MAX_T=0` などで自動既定値を抑止してもエラー終了にはならず、lookup の既定上限が 0 になります。`docs/DETAILS.md:1086` も一 GPU の 8-row CUDA serve engine で既定 12、`STRATA_LOOKUP_MAX_T=0` で停止と説明しています。測定値はここでは再掲していません。

## 根拠

- 全リポジトリでの名前の完全一致検索では、実装の環境読み取りは `src/program/generate.cpp:4144-4145` のみでした。候補一覧の名前だけやコメントは実装根拠にしていません。
- 値の既定値と条件: `src/program/generate.cpp:4143-4155`、`include/strata/core/lookup_default.hpp:9-27`。
- CLI 値の初期値・優先: `src/program/generate.cpp:972-977,3551`。
- window 上限と各サイズの graph fallback: `include/strata/kernels/window_limits.hpp:14-25`、`include/strata/kernels/verify_kernels.hpp:23-31`、`src/program/generate.cpp:13417-13437`。
- 既存の説明との照合: `docs/DETAILS.md:1086`。
