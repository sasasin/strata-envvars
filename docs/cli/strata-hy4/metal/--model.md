# `--model`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal`（Metal） |
| オプション | `--model` |
| 別名 | なし（同じ変数を設定する `--native` は別オプションとして索引化） |
| 値 | `.strata` モデルファイルのパス。parser 上の既定値は空文字列 |

## 役割

Metal 版 Hy4-Flash runner が使うモデルファイルを指定する。通常実行ではこのファイルを開き、manifest の tensor 情報を読み、Section 1 の重みを mmap して Metal buffer で参照する。ファイルサイズや Metal の buffer / working-set 上限に応じて Section 4 の expert も含む全体を扱うか、Section 1 のみを map して expert を必要時に読む cold-expert 経路へ分かれる。`--load-only` でもこのモデルの読込までは行われる。

## 使い方

```sh
# モデルを開いて読み込み可能か確認し、推論には進まない（Apple Silicon / Metal 上）
strata-hy4-metal --model /path/to/SQ64.strata --load-only
```

通常のオフライン推論では `--model` に加えて token 入力などを渡す。server 起動では `--serve` と組み合わせる。いずれもモデルの読み込みに成功してから後続処理へ進む。

## 値と既定値

- `--model` の直後の argv を文字列として受け取り、`model` に代入する。パスの存在・拡張子・内容は parser では検証しない。数値変換や既定パスへの補完もない（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1489-1507`）。
- オプションを省略した場合や空文字列を指定した場合、通常の処理開始前に usage を stderr に出して終了コード 2 で終了する（同 `:1611-1614`）。
- 複数回指定すると走査中に同じ変数へ順次代入されるため、後に現れた値が使われる（同 `:1504-1507`）。
- `--native` も同じ `model` 変数に代入する別の parser 分岐で、両方を指定したときは argv 上で後の方が残る（同 `:1589-1591`）。索引上は別オプションの文書として扱われている。
- 値を省略した場合の専用エラー処理は parser にない。`nxt()` は次の argv をそのまま参照するため、値を伴う指定が必要であり、欠落時の安全な診断はソースから確認できない（同 `:1504-1507`）。

## 実行時の動作

通常経路では `Model::load` にパスを渡す。reader はファイルを開き、`.strata` magic、4 KiB header、section 数、section offset の alignment を確認する。Metal 側 reader は Section 0 を展開しないため、モデルファイルの隣に `<モデルパス>.manifest.json` が必要で、manifest が空なら読込を拒否する。manifest を解析した後、モデルファイルを読み取り専用で open し、Metal の max buffer length と推奨 working set を使って全体 map / Section 1 のみ map を選び、Section 2 seed を読み取る（`engine/src/hy4flash/metal/strata_reader_nozstd.cpp:32-93`; `engine/src/hy4flash/metal/hy4_metal_main.cpp:214-274`）。

`--model` と `--native` は同一の値を設定する。モデルのロードは `--load-only` 判定および `--serve` 判定より先に行われるため、どちらの動作モードでもファイルを開く。serve では値が `ServeOpts::model` に渡され、会話 spill directory の既定値判定にも使われる。明示的な spill directory がなければ、session reuse が有効でパスに `/models/` が含まれる場合、その直前までのパスに `/conversation-spill` を付けた場所が選ばれる（同 `:1635-1654`; `engine/src/hy4flash/metal/hy4_metal_spill.h:71-78`）。

## 適用条件と副作用

- 対象は `strata-hy4-metal` の Metal runner である。実行時に Metal context を作成し、モデルファイルを読み取り専用で開く。全体 mmap が選ばれたときはファイル全体を map し、cold-expert 経路では Section 1 を map し、expert body は後続処理でファイル descriptor から読み取る（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1615-1629`, `:214-255`, `:663-671`）。
- `--load-only` はロード成功後に終了する。`--serve` 指定時は同じモデルをロードしてから server 処理へ進む（同 `:1635-1644`）。
- `--info FILE` は別の早期終了経路で、引数をモデル情報ファイルとして reader に渡すが、通常の `--model` ロード経路や Metal context は通らない（同 `:1575-1582`; info 処理は `:1441-1455`）。
- `--model` 自体はファイルを書き換えない。serve の会話 spill 先など、後続機能の副作用はそれぞれの条件に従う。

## 出力とエラー

- モデルパスが空なら usage を stderr に出し、終了コード 2（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1611-1614`）。
- ファイルを開けない、header が短い、magic / section 数 / alignment が不正な場合は reader がエラー理由を設定する。呼び出し側は `load: <理由>` を stderr に出し終了コード 1（`engine/src/hy4flash/metal/strata_reader_nozstd.cpp:32-66`; `engine/src/hy4flash/metal/hy4_metal_main.cpp:1619-1623`）。
- 隣接 manifest がない、または空の場合は sidecar の必要性を含む `load: no manifest: ...` を stderr に出し終了コード 1（`engine/src/hy4flash/metal/hy4_metal_main.cpp:217-222`）。manifest の JSON / 必須キーが不正な場合の例外・終了表示は、この呼出し経路について調査したソース範囲からは特定できない。
- 二度目の `open`、mmap、Section 2 読込にも失敗経路があり、前者は `load: open <path>`、mmap は `load: mmap failed` または `load: mmap sec1 failed`、section 読込は `load: <reader error>` として終了コード 1 になる（同 `:228-256`, `:1619-1623`）。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1488-1515` — `--model` の parser 登録、空の初期値、後続 argv の代入。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1589-1614` — `--native` の同変数への代入、モデル未指定時の usage と終了コード。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:214-274` — 指定パスの reader / manifest / mmap / seed 読込と失敗経路。
- `engine/src/hy4flash/metal/strata_reader_nozstd.cpp:32-93` — Metal reader の `.strata` header 検証と隣接 manifest の読込。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1615-1654` — 通常ロード後の `--load-only` / `--serve` 分岐、serve へのパス引渡し。
- `engine/src/hy4flash/metal/hy4_metal_spill.h:71-78` — serve の session reuse 時にモデルパスから spill root を決める条件。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1575-1582`, `:1441-1455` — `--info` の別経路。
