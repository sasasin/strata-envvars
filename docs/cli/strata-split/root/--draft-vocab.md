# `strata-split-N --draft-vocab`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。Strata checkout は `main`（`origin/main` と一致）で、調査開始時の `git status --short --branch` は `## main...origin/main` でした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-split` |
| コマンド | `strata-split-N`（N はカード数別 executable） |
| オプション | `--draft-vocab` |
| 別名 | なし |
| 値 | draft vocabulary ファイルのパス |

## 役割

MTP draft head の行と native model の token ID を対応付ける語彙ファイルを指定します。`strata-split` は起動時にこのファイルを読み、MTP の初期化へ渡します。通常の MTP runtime では省略時に runtime directory 内の `draft_vocab.bin` が使われます。27B build では model に draft layer 自体が含まれるため、語彙ファイルの明示指定が必要です（`src/split/tools/sfnx.cpp:65-67,84,1055-1059`、`src/split/src/model.hpp:220-225`、`src/split/src/model.cpp:1142-1149,1193-1198`）。

## 使い方

```sh
strata-split-2-sm90 --serve --native ./model.gguf --mtp ./mtp-runtime \
  --draft-vocab ./mtp-runtime/draft_vocab_en.bin
```

ここで `strata-split-2-sm90` はカード数・GPU architecture に合う実行ファイル名の例です。実際の起動では `--serve`、`--native`、`--mtp` も必要です。Terminal の起動経路は語彙ファイルを検出し、そのパスを `--draft-vocab` の値として組み立てます（`strata_control/split_engine.py:494-509`）。

## 値と既定値

- parser は次の argv 要素を値として受け取ります。値を省略すると `--draft-vocab needs a value` になります。値の内容やファイルの存在確認は parser 段階では行わず、同じ option を複数指定したときは `Args` への後続代入で前の値を置き換えます（`src/split/tools/sfnx.cpp:72-85`）。
- 通常の MTP build では、値が空（option を省略した場合を含む）なら `<--mtp で指定した runtime directory>/draft_vocab.bin` を開きます。空でない値はそのパスを直接開きます（`src/split/src/model.cpp:1193-1198`）。
- `FNX_27B` build では省略・空値はエラーになり、非空の明示パスが必要です。`--mtp` の値は `nextn` でなければなりません（`src/split/src/model.cpp:1142-1149`）。
- ファイルは raw な int32 token ID の列として読み込まれます。サイズが 4 の倍数であること、読み切れること、空でないこと、各 ID が `0 <= id < model vocab size` であることを検証します（`src/split/src/model.cpp:1149-1165,1196-1213`）。
- ソースでは ID の重複を拒否していません。読み込んだ列の各 ID から draft head の行番号への map を構築し、重複 ID は後の行番号で上書きします（`src/split/src/engine.cu:1231-1232`）。

## 実行時の動作

`sfnx` は `--draft-vocab` の値を `Args::draft_vocab` に格納し、モデルを読み込んだ後 `fnx::Mtp` のコンストラクタへ `--mtp` の値とともに渡します（`src/split/tools/sfnx.cpp:82-84,1055-1059`）。コンストラクタは語彙ファイルを読み、MTP head の各行に対応する token ID の列を作ります。engine はその列から token ID → draft head 行番号の index を作成し、draft 処理や penalty の対応付けに使います（`src/split/src/model.cpp:1194-1226`、`src/split/src/engine.cu:1231-1232`、`src/split/src/engine_common.cu:1398-1407,1531-1540`）。

この option は `--mtp` と連携します。`--mtp` 自体は parser で必須とされますが、`--draft-vocab` は parser では必須扱いではありません。通常 build では `--mtp` directory の既定ファイルが使われ、27B build では明示値が必要です（`src/split/tools/sfnx.cpp:101`、`src/split/src/model.cpp:1145-1149,1194-1198`）。

## 適用条件と副作用

語彙ファイルは engine 起動時に読み取られます。値を変更すると、同じ MTP runtime / model に対して draft head が参照する token ID の対応が変わります。読み込み時にファイルを開いて読む以外の書き込み処理はこの経路にはありません（`src/split/tools/sfnx.cpp:1055-1059`、`src/split/src/model.cpp:1149-1165,1196-1213`）。

Terminal の `strata launch` 経路は、engine executable の隣、data directory、設定上の `cwd/data` の順に `draft_vocab_en.bin` を探し、見つからない場合は split engine を使わない判定を返します。この経路では検出したファイルを明示値として渡すため、通常 build の `draft_vocab.bin` 既定値とは異なる指定になります（`strata_control/split_engine.py:501-509`）。

## 出力とエラー

- option の値が無ければ parser が例外を投げ、`main` は stderr に `sfnx: <理由>` を出して status 2 で終了します（`src/split/tools/sfnx.cpp:77-79,1038-1048`）。
- ファイルを開けない、サイズが int32 境界でない、読み込み途中の I/O error、空ファイル、model vocab 範囲外の token ID は MTP 初期化時に例外になります。起動時の初期化失敗経路は stdout に `ERR <理由>`、stderr に `sfnx: failed: <理由>` を出して status 1 で終了します（`src/split/src/model.cpp:1149-1165,1196-1213`、`src/split/tools/sfnx.cpp:1038-1061`）。
- 27B build で語彙パスが空の場合は `mtp: the 27B needs a draft vocabulary file`、`--mtp` が `nextn` 以外の場合はその指定を示すエラーになります（`src/split/src/model.cpp:1145-1148`）。

## 根拠

- parser、値の代入、必須の関連引数: `src/split/tools/sfnx.cpp:65-104`
- MTP 初期化への引き渡しと起動失敗時の出力: `src/split/tools/sfnx.cpp:1038-1061`
- 27B build と通常 build のファイル選択・検証: `src/split/src/model.cpp:1142-1235`、宣言コメント `src/split/src/model.hpp:220-225`
- 語彙 index の構築と利用: `src/split/src/engine.cu:1231-1232`、`src/split/src/engine_common.cu:1398-1407,1531-1540`
- Terminal がこの値を組み立てる経路: `strata_control/split_engine.py:250-270,494-509`
