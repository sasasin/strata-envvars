# `STRATA_MTP_FULL_HEAD`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

MTP drafter がドラフト候補を計算するとき、`rt/draft_vocab.bin`（または `--mtp-draft-vocab FILE`）で選んだ語彙部分集合を使わず、native model の出力 head 全体を使う診断用スイッチである。CUDA/HIP 実装と SYCL 実装の両方で、部分集合 head のロードを飛ばし、ドラフト head の行列積に native head の重みを渡す。ドラフト候補の語彙幅は部分集合の件数でなくモデル全体の語彙数になる（`engine/src/core/mtp.cpp:939-945,1516-1519`、`engine/sycl/src/core/mtp.cpp:612-617,820-825`）。

これは MTP が使われる実行経路にだけ関係し、MTP 自体を有効にはしない。`--mtp` と `--spec T`（`T >= 2`）が必要で、`--spec` が足りないと `--mtp` は無視される（`engine/src/program/generate.cpp:8243-8247`）。Metal では共通 `MtpDrafter::bind` が即時 return するため、この bind 内の部分集合選択は実行されない（`engine/src/core/mtp.cpp:908-913`）。

## 値と判定

CUDA/HIP 共通実装および SYCL 実装では、`std::getenv` の戻り値が null でなく、かつ先頭文字が `'1'` かだけを関数内 `static const bool` に保存する。文字列全体の parse・比較はしない（`engine/src/core/mtp.cpp:693-696`、`engine/sycl/src/core/mtp.cpp:615-618`）。

| 判定箇所 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| MTP の subset 読み込み抑止・full-head 動作 | full head モードではない | 先頭が `1` の値（`1`, `10`, `1anything`） | 空文字、`0`, `0anything`, `true`, ` 1` など |
| `mtp_first_ok`（layer split で drafter を最初の stage に置く判定） | subset file の有無など他条件を評価 | 先頭が `1` なら配置不可 | 先頭が `1` でなければこの変数による拒否なし |
| DFlash2 の MTP head 共有見積もり | 共有候補になり得る | 値を問わず「設定あり」として共有見積もりを無効化 | 該当なし（空文字を含め、設定されていれば無効） |

MTP 側の読み取りは初回呼び出し時に `static` へ cache され、そのプロセス中の環境変更は反映されない。対して `generate.cpp` の2箇所は初期化時に直接 `getenv` し、MTP 側の先頭文字判定と、DFlash2 見積もり側の設定有無判定は別の規則である（`engine/src/program/generate.cpp:6540-6546,8408-8410`）。大文字小文字や数値としての妥当性は検査しない。

## 有効になる条件

- `--mtp` が指定され、`--spec` が 2 以上であること。MTP がロードされない経路では MTP 側の full-head 動作はない（`engine/src/program/generate.cpp:8243-8253,8264`）。
- CUDA/HIP または SYCL の MTP 実装であること。CUDA/HIP の `engine/src/core/mtp.cpp` と SYCL の `engine/sycl/src/core/mtp.cpp` は同じ先頭文字判定を持つ。Metal は共通 bind 内の subset 読み込みに進まない（`engine/src/core/mtp.cpp:908-913`）。
- `--mtp-draft-vocab FILE` や `<mtp>/draft_vocab.bin` が存在しても、full-head 判定が有効なら MTP はその subset を読み込まず、通常の subset head は作らない。値が無効または未設定なら、通常どおりファイルの存在と内容が処理される（`engine/src/core/mtp.cpp:939-945`、`engine/sycl/src/core/mtp.cpp:820-825`）。
- layer split で drafter を最初の stage に置くには、別途 `--mtp`、`--spec >= 2` と draft vocabulary ファイルが必要であり、変数が先頭 `1` の場合は `mtp_first_ok` が false になる（`engine/src/program/generate.cpp:6538-6546`）。
- `STRATA_MTP_FULL_HEAD` が設定されていると、値が空または先頭が `1` 以外でも `df2_expect_share` は false になる。この変数は MTP の full-head 判定とは異なり、DFlash2 の head 共有を見込むメモリー見積もりを抑止する条件である（`engine/src/program/generate.cpp:8404-8410`）。

## 実行時の詳細

MTP の `full_head_env()` は `bind_bytes()` と `bind()` の subset 処理より前に参照される。初回参照時に環境値を一度だけ読む。full-head が有効なら `bind_bytes()` は subset head の追加バイトを見積もらず、`bind()` は語彙ファイルからの ID 読み込み・native head 行の gather を行わない（`engine/src/core/mtp.cpp:772-780,939-945`、`engine/sycl/src/core/mtp.cpp:654-669,820-825`）。

ドラフト計算では `dhead_ == nullptr` のため、native head の全語彙行と全語彙数が使われる。部分集合 ID への逆写像も行わず、候補 ID はそのまま全語彙の ID として扱われる（`engine/src/core/mtp.cpp:1516-1543`）。この設定は MTP の候補計算を変えるもので、別の verifier をなくしたり MTP の起動条件を置き換えたりはしない。

MTP の head share は subset が実際にロードされている場合に限り可能であり、`draft_head_view()` は `dhead_` と `dvocab_` がないと false を返す。したがって full-head では DFlash2 へ subset head を渡さない（`engine/src/core/mtp.cpp:789-799`、`engine/src/program/generate.cpp:8411-8418`）。ただし `df2_expect_share` のメモリー見積もりは環境変数の設定有無だけを条件にするため、空文字や `0` でも共有を見込まない。

## ログと測定値

この変数専用の有効ログや無効値警告はない。`--mtp-q4 head` または `--mtp-q4 all` と組み合わせ、subset head がない場合は stderr に次の警告を出す。これは full-head 設定だけでなく、subset ファイルが不在または空の場合にも出る。

```text
strata mtp: --mtp-q4 head/all has no effect: it requantizes the draft head's subset, and none is installed (rt/draft_vocab.bin or --mtp-draft-vocab FILE is absent or empty, or STRATA_MTP_FULL_HEAD=1 excludes it); drafting runs over the full head. Install a subset (tools/draft_vocab.py) to use it
```

subset 読み込みの失敗をこの変数が直接エラーにすることはない。full-head 経路では subset の割り当て・gather が省かれる一方、native head と MTP logits の確保は別途必要であり、確保失敗時には通常の MTP エラー経路となる（`engine/src/core/mtp.cpp:921-925,939-951,1007-1014`）。この変数による性能測定値は、調査対象ソース・資料から確認できない。

## 根拠

- `engine/src/core/mtp.cpp:691-696` — CUDA/HIP 側の値判定と static cache。
- `engine/sycl/src/core/mtp.cpp:612-618` — SYCL 側の値判定と static cache。
- `engine/src/core/mtp.cpp:772-780,908-945`、`engine/sycl/src/core/mtp.cpp:654-669,790-825` — subset のメモリー見積もりと bind 時の読み込み条件。
- `engine/src/core/mtp.cpp:1516-1543` — subset がない場合に full vocabulary でドラフトを計算する経路。
- `engine/src/program/generate.cpp:8243-8253,8264` — `--mtp` / `--spec` 条件と MTP のロード。
- `engine/src/program/generate.cpp:6538-6546,8404-8418` — layer split 配置と DFlash2 head 共有見積もり・提供条件。
- `engine/src/core/mtp.cpp:1007-1014` — `--mtp-q4` と subset 不在時の警告および bind の失敗伝播。
