# `STRATA_MMQ_DIRECT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

この checkout で環境から値を読む箇所は、`STRATA_EXPERT_NIBBLE=1` の起動可否を調べる `nib::env_conflicts()` にある。値が非ゼロなら、4-bit expert slot を GGUF block として読む prompt MMQ と競合すると判定し、`STRATA_EXPERT_NIBBLE` をその起動に限って無効にする。通常の生成をこの変数が直接切り替える読み取り箇所は確認できない。`engine/include/strata/prefill/moe_mmq.hpp` などには MMQ の in-place 読み取りを説明する記述があるが、現行ソース全体で `STRATA_MMQ_DIRECT` を `getenv` や env helper に渡す MMQ 制御の呼び出しは見つからなかった。実際に確認できる読み取りと分岐は `engine/include/strata/core/expert_nibble.hpp:277-298` である。

## 値と判定

`env_conflicts()` 内の `set` helper は `std::getenv(n)` を呼び、未設定または空文字列なら `nullptr` として扱う。`STRATA_MMQ_DIRECT` の値が非空の場合だけ `std::atoi(v) != 0` を調べ、真なら競合理由を返す（`engine/include/strata/core/expert_nibble.hpp:277-284`）。文字列全体の数値検証はせず、`atoi` の整数接頭辞変換に従う。したがって、例として `1`, `2`, `-1`, ` 1x` は非ゼロ、`0`, `0anything`, `true`, 空文字列、未設定はこの条件を満たさない。大文字小文字の比較や範囲 clamp はない。

| 条件 | unset | 競合になる値 | 競合にならない値 |
|---|---|---|---|
| `STRATA_EXPERT_NIBBLE` の起動判定で helper が呼ばれる場合 | 競合なし | `atoi` が非ゼロを返す非空文字列（例 `1`, `-1`, ` 1x`） | 空文字列、`atoi` が 0 を返す文字列（例 `0`, `0anything`, `true`） |
| `STRATA_EXPERT_NIBBLE` を要求しない場合 | 読み取りなし | 該当なし | 該当なし |

## 有効になる条件

- `STRATA_EXPERT_NIBBLE` が設定値 `1` で要求されていること。設定の判定は `config()` に一度だけ保存され、空文字列と文字列 `0` は off、文字列 `1` は on、それ以外の非空値は設定エラーになる（`engine/include/strata/core/expert_nibble.hpp:238-268`）。`nib::env_conflicts()` は `nibble_refusal()` の中から呼ばれるため、nibble を要求しない通常起動ではこの変数も読まれない（`engine/src/program/generate.cpp:3408-3413, 3430, 5474-5478`）。
- ビルドが nibble 対応でない場合や、CUDA デバイスがない／全 CUDA デバイスが compute capability 6.0 でない場合、`nibble_refusal()` は環境競合 helper より先に理由を返す。その場合、この呼び出しでは `STRATA_MMQ_DIRECT` の値を調べない（`engine/src/program/generate.cpp:3411-3430`）。
- helper が実行され、`STRATA_MMQ_DIRECT` が非空かつ `atoi` 非ゼロなら、`nib::env_conflicts()` は他の環境変数判定より先にこの競合理由を返す。後続には `STRATA_PREFILL_MMQ`、`STRATA_PF_FUSED`、`STRATA_FS_SLOTS`、`STRATA_EXPERT_V2`、`STRATA_KV_GROW`、`STRATA_EXP_MODE` の判定がある。CLI の `--peer-device`、remote expert cache、`--kv-grow`、`--vram-elastic` の判定はこの helper の後に行われる（`engine/include/strata/core/expert_nibble.hpp:282-298`; `engine/src/program/generate.cpp:3430-3440`）。
- この変数単独で expert cache の容量、prompt の MMQ 経路、生成 token の選択を変える動作は確認できない。`direct_mode()` の呼び出しはあるが、リポジトリ内で見つかった実装定義は MMQ 非搭載時の stub で、いずれも `0` を返す。MMQ 搭載時の実装を含む `STRATA_MMQ_DIRECT` の直接読取箇所は現行ソースから確認できない（`engine/src/prefill/prefill.cpp:144-178`; `engine/src/prefill/mmq_absent.cpp:38-45`）。

## 実行時の詳細

`nib::env_conflicts()` はキャッシュしない helper で、呼ばれるたびに環境を読み直す。ただし確認した呼び出し元 `nibble_refusal()` は `generate.cpp` の起動処理で `STRATA_EXPERT_NIBBLE` が要求された場合に一度呼ばれるため、生成中の環境変更を反映する経路はない。非ゼロ値が競合理由になった場合、呼び出し元は nibble layer 設定を消し、起動を拒否せず GGUF block の expert slot のまま処理を続ける（`engine/src/program/generate.cpp:5474-5489`）。

変数名を含む他の参照は、cache の slot guard、MMQ pointer table、prompt の統計や設定登録に関するコメント・宣言・ログ文字列である。これらの記述や `direct_mode()` の利用箇所だけから、`STRATA_MMQ_DIRECT` が in-place MMQ 読み取りを有効にすると断定できる環境読取実装は確認できない。特に `direct_mode()` の具体的な定義として追えたものは MMQ がない場合の stub のみであり、この checkout ではその制御の値判定や有効条件を裏付けられない（`engine/include/strata/prefill/moe_mmq.hpp:146-172`; `engine/src/prefill/prefill.cpp:149-177`; `engine/src/prefill/mmq_absent.cpp:38-45`）。

## ログと測定値

非ゼロ値が nibble の起動判定で競合した場合、stderr に次の警告を出し、この起動では nibble を off にして続行する。

```text
strata generate: WARNING: STRATA_EXPERT_NIBBLE is off for this start: STRATA_MMQ_DIRECT (the prompt MMQ would read a converted slot in place as GGUF blocks); the expert slots stay GGUF blocks
```

実装の書式文字列は `engine/src/program/generate.cpp:5485-5489`、理由文字列は `engine/include/strata/core/expert_nibble.hpp:282-284`。この変数による直接 MMQ 動作や性能測定値を記述した、現行ソースと条件を照合できる Strata 資料は確認できなかったため、測定値は記載しない。

## 根拠

- `engine/include/strata/core/expert_nibble.hpp:277-298` — `getenv` を呼ぶ helper、空文字の除外、`atoi` 判定、理由文字列と他環境変数との判定順。
- `engine/src/program/generate.cpp:3408-3440, 5474-5489` — 起動時の呼び出し条件、先行条件、警告後に nibble を無効にして続行する処理。
- `engine/src/prefill/prefill.cpp:149-178`; `engine/src/prefill/mmq_absent.cpp:38-45` — 確認できた MMQ fallback stub の定義。
- `engine/include/strata/prefill/moe_mmq.hpp:146-172`; `engine/src/prefill/prefill.cpp:2142-2161, 7111-7113` — MMQ direct 機能に関する宣言・利用側の参照。ただし環境値の直接読取実装を示す箇所ではない。
