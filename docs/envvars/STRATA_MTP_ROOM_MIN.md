# `STRATA_MTP_ROOM_MIN`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`--serve` の MTP 付き実行で、要求が新たに読むプロンプト token 数が指定値以上なら、MTP drafter が所有する routed expert の VRAM 領域を、その要求の prompt prefill ring の追加 slot として一時的に使います。expert block は解放・再確保・移動せず、プロンプト読込後に内容を戻して decode に返します。通常の prompt ring の slot 数や prefill の token 内容を直接指定する変数ではありません。実装は `engine/src/program/generate.cpp` の serve 初期化と要求処理です（`engine/src/program/generate.cpp:12848-12889, 20187-20204`）。

候補名の全参照を調べた結果、実際に環境から値を読む箇所は `generate.cpp:12859` の `std::getenv` です。同ファイルの他の参照および `mtp.hpp`・`prefill.hpp` の参照はコメントやエラー文で、別の読み取りや helper 経由の参照はありません。読み取った値は Strata 内で数値判定され、要求時の条件分岐に使われます（`engine/src/program/generate.cpp:12858-12889, 13019-13044, 20187-20204`）。

## 値と判定

`std::getenv` の結果を serve の prompt path 初期化時に一度読み、`std::strtoll(v, &end, 10)` で基数 10 の `long long` に変換します。未設定と空文字はどちらも `-1`（無効化）です。変換できる数字がない、末尾に `\0` 以外の文字が残る、または変換結果が負なら無効値 `-2` となり、stderr にエラーを出して `return 2` します。`strtoll` が許す先頭空白と `+` は受け付けますが、数値の後の空白は末尾文字として拒否されます。`errno` は確認しないため、正の範囲外入力は `strtoll` の返す上限値になり、閾値として受理されます（実際の prompt 長を超える通常の要求では発動しません）。

| 条件 | unset / 空文字 | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| serve 初期化時 | 無効。room slot は 0 のまま | `0`（全要求が閾値を満たす）、`-0`（変換結果は 0）、`1`、`+12`、` 12` | `-1`、`true`、`12x`、`12 `、空白のみ |

`0` 以上の値は閾値として受理されます。数値全体の parse なので `0anything` は無効です。大小文字は文字列フラグ比較に使わないため関係しません。CLI から閾値を上書きする引数はこの実装にありません。`--serve`、`--mtp` は機能の必須条件であり、`--batch` は非対応として拒否されます（`engine/src/program/generate.cpp:12871-12889`）。

## 有効になる条件

設定値が有効でも、次の条件を満たさない要求では追加 room を使いません。

- `--serve` かつ `--mtp` が必要です。どちらかがない場合は stderr に理由を出し、serve 初期化を `return 2` で終了します（`engine/src/program/generate.cpp:12872-12880`）。
- `--batch` は使えません。batch slot drafter が drafter の重みを共有するためとして、同じく初期化を `return 2` で終了します（`engine/src/program/generate.cpp:12874-12880`）。
- drafter 自身が 512 experts を所有し、貸し出せる必要があります。共有重みなどで `mtp.experts_bytes() == 0` なら初期化エラーです（`engine/src/program/generate.cpp:12876-12880`; 所有条件は `engine/src/core/mtp.cpp:724-728`）。
- prompt path が存在し、drafter と同じ GPU 上にある必要があります。どの path も drafter の device にない場合は stderr にその旨を出し、その prompt は自身の ring で読みます（`engine/src/program/generate.cpp:13019-13044`）。
- 要求が読む token 数 `n - read_from` が閾値以上である必要があります。`read_from` は再利用する prefix の位置であり、会話全体の長さ `n` ではありません（`engine/src/program/generate.cpp:20187-20204`）。
- prompt ring の layout に room が作れる必要があります。`Prefill` は通常 ring が `STAGE` より大きく、room base があり、ring cap と lender の bytes 内に slot が残る場合だけ room を設定します。該当しない layout では値を満たしても追加 slot がありません（`engine/src/prefill/prefill.cpp:2865-2883`; room の用途・容量制約は `engine/include/strata/prefill/prefill.hpp:152-167`）。

`STRATA_MTP_ROOM_MIN` 自体の読み取りには backend 分岐がありません。コードは CUDA API と CUDA device を使う prompt / MTP path です。Strata の `docs/DETAILS.md` も対象を CUDA と記しますが、`docs/SETTINGS.md` の一覧行は「NVIDIA and AMD」となっており、表記が一致しません。設定一覧だけから AMD 実装を確認したとは扱えません。

## 実行時の詳細

変数は serve の初期化中に一度読みます。各 request で環境を再読せず、プロセス起動後の環境変更は反映されません（`engine/src/program/generate.cpp:12858-12865, 20187-20204`）。閾値に達した要求では、prompt path の ring を有効にする前に `MtpDrafter::experts_lend` が expert block を pinned host memory にコピーします。コピーに失敗すれば理由を stderr に出しますが、その要求は従来どおりに読み進めます。貸出成功後は room を有効にし、その要求の prompt 読み込み中だけ ring の slot 数に加えます（`engine/src/program/generate.cpp:20191-20204`; `engine/src/core/mtp.cpp:730-755`; `engine/src/prefill/prefill.cpp:2972-2977`）。

expert block は VRAM 上の同じアドレスに残り、room slot が prefill 中にその bytes を使います。expert bytes を貸し出している間、decode entry は誤って prefill data を expert として読むのを拒みます（`engine/include/strata/core/mtp.hpp:92-108, 267-272`）。prompt 完了時は stream が idle であることを確かめ、ring の room を閉じてから experts を同じ VRAM address に戻します。前の request が room を開いたまま残った場合も次の要求処理前に閉じます（`engine/src/program/generate.cpp:19157-19163, 19205-19220, 21625-21630`; `engine/src/core/mtp.cpp:758-769`）。

## ログと測定値

- 無効値: stderr に `strata generate: STRATA_MTP_ROOM_MIN=%s is not a token count (0: every request)` を出し、初期化を `return 2` で終了します（`engine/src/program/generate.cpp:12866-12870`）。
- 利用条件不足: stderr に `strata generate: STRATA_MTP_ROOM_MIN is unavailable: ...` と条件ごとの理由を出し、`return 2` で終了します（`engine/src/program/generate.cpp:12872-12880`）。
- 有効な非負値: 閾値と expert MiB / slot 数を `strata serve: STRATA_MTP_ROOM_MIN=...` の行で stderr に出します。設定ログは、個々の要求が閾値に達したかや room が使われたかを示すものではありません（`engine/src/program/generate.cpp:12882-12889`）。
- 要求時: 成功時は読込 token 数、slot 数、貸出時間を `strata serve: prompt room: ...` に記録します。貸出失敗時は理由と「this prompt reads as it always did」を記録します。完了時には返却時間を記録します（`engine/src/program/generate.cpp:20191-20204, 19205-19218`）。drafter device に prompt path がなければ `strata serve: prompt room: no prompt path runs ...` を出します（`engine/src/program/generate.cpp:13042-13044`）。
- Strata の `docs/DETAILS.md:1280` は特定 GPU での prompt 速度測定を記載していますが、モデル・量子化などの条件が記載されていないため、この文書では測定値として採用しません。

## 根拠

- `engine/src/program/generate.cpp:12848-12889` — 環境読み取り、数値変換、CLI / ownership 条件、初期化ログ。
- `engine/src/program/generate.cpp:13019-13044` — drafter device の prompt path に room layout を設定する処理。
- `engine/src/program/generate.cpp:19157-19220, 20187-20204, 21625-21630` — prefix 再利用を考慮した閾値判定、貸出・返却、要求完了時の処理。
- `engine/src/prefill/prefill.cpp:2865-2883, 2972-2977` — room slot の layout、容量上限、active 時の ring count。
- `engine/src/core/mtp.cpp:724-769`; `engine/include/strata/core/mtp.hpp:92-108, 267-272`; `engine/include/strata/prefill/prefill.hpp:152-177` — lender の所有条件、expert block の貸出・復元、および room の安全条件。
