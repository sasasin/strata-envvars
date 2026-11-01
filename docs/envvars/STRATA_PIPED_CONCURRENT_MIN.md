# `STRATA_PIPED_CONCURRENT_MIN`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `## main...origin/main` で、未コミット変更はありませんでした。

## 役割

`STRATA_PIPED_CONCURRENT=1` で opt-in するパイプライン並列 prompt read に、token 数の下限を設けます。値は並列読み取り自体を有効にせず、対象の prompt read 区間が下限未満なら通常の読み取り経路へ進ませます。下限が 0 なら、並列読み取りの他の条件を満たすすべての区間が対象です。

この分岐は、`--batch` が正で、`--batch-groups` が 1 より大きく、layer split の stage が複数ある pipelined batch path にあります。Strata の BATCHING 文書は、この親機能を実験的な opt-in とし、CUDA/HIP でビルドされ SYCL では利用できないと説明しています（`docs/BATCHING.md:225-259`）。

## 値と判定

実装は `std::atoll` で符号付き整数に変換し、その結果と 0 の大きい方を `int64_t` として使います。文字列全体の妥当性検査やエラー報告はありません。

| 環境変数の値 | 閾値として使われる値 |
|---|---:|
| 未設定 | 0 |
| 空文字 | 0（`atoll` の変換結果 0） |
| 10 進数の非負整数（例 `4096`） | 変換された整数 |
| 負の整数（例 `-5`） | 0（負値を clamp） |
| 数字で始まらない文字列 | 0（変換結果 0） |
| 数字の後に別の文字が続く文字列（例 `12tail`） | 数字の接頭部分 12 |

したがって `0`、負値、空文字、非数値文字列は、いずれも全区間を許す 0 の閾値になります。`atoll` の変換範囲を超える入力について、Strata 独自の検査・fallback はありません。

実際の条件は `(b0 - a0) >= pr_conc_min` です。等しい場合も条件を満たし、1 token でも下回ればこの並列経路を通りません。ここで比較するのは `read_part` に渡された区間長で、必ずしもキャッシュ再利用後の元 prompt 全長ではありません（`src/program/generate.cpp:15133-15171,15406-15413`）。

## 有効になる条件

次の条件をすべて満たす必要があります。

- pipelined batch path である（`--batch > 0`、`--batch-groups > 1`、かつ `n_pipe > 1`）。`n_pipe` は layer split の stage 数に 1 を足した数です（`src/program/generate.cpp:13012-13016`）。
- `STRATA_PIPED_CONCURRENT` が設定され、`atoi` の結果が 0 ではない。未設定・空文字・`0` や非数値文字列では親機能が無効で、MIN を設定しても有効化されません（`src/program/generate.cpp:15383-15405`）。
- `STRATA_PREFILL_HELP`、`STRATA_SPLIT_MTP_BATCH`、`STRATA_FS_SLOTS` が `atoi` で非 0 ではなく、`--pcie-mode dma` でもない。
- helper cache を使っておらず、GGUF source が blob を stage する状態でもなく、GGUF source と arena source 以外の expert source でもない。これらの条件に当たると親機能は無効になり、stderr に `strata batch: STRATA_PIPED_CONCURRENT is off beside ...` が出ます（`src/program/generate.cpp:15386-15402`; 判定内容は `include/strata/program/batch_read.hpp:30-53`）。
- request に画像がない。
- 対象区間の token 数が閾値以上である。

CLI 引数・設定ファイル・他の環境変数が MIN の値を上書きする経路はありません。`STRATA_PIPED_CONCURRENT` は独立した必須 opt-in です。親機能が有効で区間が閾値未満、または画像付きの場合は、この専用並列読み取りブロックを通らず、その後の通常の piped read 処理へ進みます（`src/program/generate.cpp:15413-15414,15637-15706`）。

## 実行時の詳細

`pr_conc_min` は関数内の `static const int64_t` です。最初にこの宣言まで実行が到達した時に環境を読み、その後の同一プロセスでは値を再評価しません。起動後に環境を書き換えても反映されません（`src/program/generate.cpp:15409-15412`）。親 opt-in の `pr_conc` も同じく static cache です（同:15383-15405）。

閾値以上の区間では、Strata は prompt の upload buffer を事前確保し、prompt を専用 reader thread で読みながら、別 thread で pipelined slot groups の window doorbell を処理して pump を続けます。読み取り終了後に pipeline を drain します（`src/program/generate.cpp:15413-15421,15472-15534,15535-15607`）。この動作自体は `STRATA_PIPED_CONCURRENT` の説明にある機能で、MIN が変えるのはこの経路へ入る区間の長さの条件です。

- 並列読み取りが完了すると stderr に `strata batch: read N tokens on a thread of its own ... (concurrent, ...)` の行が出ます（`src/program/generate.cpp:15621-15627`）。
- prompt read が失敗した場合は `read_err` を呼び出し元へ返し、この処理は `false` になります（同:15549-15560,15628-15630）。要求処理側は stderr に `strata serve: <error>`、stdout に `ERR <error>` を出し、通常は終了コード 1 で要求処理を終えます（同:15932-15965）。
- pipelined window の実行または drain が失敗すると `batch_fatal` を設定し、`a pipelined batch window failed` をエラーとして返します（同:15604-15607）。この場合も上記の要求処理側のエラー出力・終了経路を通ります。
- 閾値未満を理由とする専用ログや警告はありません。`STRATA_PIPED_CONCURRENT` 自体が他条件で無効になった場合は、前述の `off beside ...` ログが出ます。

`docs/BATCHING.md:231-259` は親機能の適用条件・挙動・ログを説明していますが、`STRATA_PIPED_CONCURRENT_MIN` の閾値と変換規則は記載していません。`tools/par/variants/p2_conc.txt:2-4` 等には `4096` と `12000` の実験設定がありますが、これらの設定行だけから性能効果は判断できません。

## 根拠

- 参照候補の全検索では、実装上の環境読み取りは `src/program/generate.cpp:15409-15412` の `std::getenv("STRATA_PIPED_CONCURRENT_MIN")` のみでした。その他の完全一致は `tools/par/variants/*.txt` の実験設定です。コメントは同ファイル `15406-15408` にあります。
- 閾値との比較と適用条件: `src/program/generate.cpp:15413-15414`。
- pipelined path の定義: `src/program/generate.cpp:13012-13016`。
- 親 opt-in の変換、除外条件、警告: `src/program/generate.cpp:15383-15405`; `include/strata/program/batch_read.hpp:30-53`。
- 並列 reader / window 処理、ログ・失敗経路: `src/program/generate.cpp:15413-15421,15472-15534,15535-15630,15932-15965`。
- 既存の親機能の説明: `docs/BATCHING.md:225-259`。
