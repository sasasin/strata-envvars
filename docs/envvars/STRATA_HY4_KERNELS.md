# `STRATA_HY4_KERNELS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`strata-hy4-metal` が実行時にコンパイルする HY4 Metal カーネルの起点ファイル（`hy4.metal`）を指定する。指定ファイルと同じディレクトリにある複数の `.metal` ファイルもコンパイル対象になる。値は有効・無効のフラグではなく、ファイルパスとして使われる。通常は `--kernels` 引数、環境変数、埋め込みカーネル、既定パスの順に候補が決まるが、環境変数が空文字のときの fallback は offline 実行と `--serve` で異なる。実装は Apple Silicon 向け Metal runner の `main` と `Runner::init` にある（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1-6,523-556,1488-1512,1661-1674,1708-1720`）。

## 値と判定

`getenv("STRATA_HY4_KERNELS")` の戻り値が null かどうかだけを調べ、null でなければ文字列をそのまま `kernels` に代入する。空文字を含め、文字列の parse、存在確認、空白除去、大小文字変換は環境変数の読み取り時には行わない。実際のファイルへのアクセスは後続の Metal compile に委ねられる。選ばれた `kernels` に `realpath` が成功すれば絶対パスへ置き換えるが、失敗してもエラーにはせず元の文字列を使う（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1661-1674,1708-1718`）。

| 実行経路 | unset | 設定時に使われる値 | 空文字・無効なパス |
|---|---|---|---|
| Offline（`--serve` なし） | `HY4_EMBED_KERNELS` ビルドなら埋め込みファイルを展開した `hy4.metal`。それ以外、または展開に失敗した場合は `hy4.metal` | `--kernels` が空でなければその CLI 値。そうでなければ環境変数の文字列 | 空文字は embedded 展開を試さず、その後 `hy4.metal` に置き換わる。無効な非空パスは fallback せず compile に進む |
| `--serve` | `HY4_EMBED_KERNELS` ビルドなら埋め込みファイルを展開した `hy4.metal`。それ以外、または展開に失敗した場合は実行ファイル隣の `hy4.metal` を試し、読めなければ `hy4.metal` | `--kernels` が空でなければその CLI 値。そうでなければ環境変数の文字列 | 空文字は embedded 展開や既定パス選択を行わず、空のまま serve の初期化に渡る。無効な非空パスも fallback せず compile に進む |

この変数の `0`、`1`、`true`、`false`、`0anything` などに特別な意味はなく、いずれも非空ならパス文字列として扱われる。相対パスも受け付け、`realpath` が解決できなければ相対文字列のまま残る。CLI の `--kernels` は引数をそのまま受け、空文字を渡した場合は「未指定」と同じ扱いになるため、環境変数が設定されていればそちらが選ばれる（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1511,1661-1671,1708-1712`）。

## 有効になる条件

- `strata-hy4-metal` の Metal 実行経路で、モデル読み込み後に offline 推論または `--serve` を開始すること。`--version`、`--info`、`--export-tokenizer`、`--load-only` など、そこで `main` を抜ける経路では読み取り箇所に到達しない（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1575-1588,1611-1614,1635-1637,1661-1674,1708-1720`）。
- `--kernels` に空でない値を渡すと CLI のパスが優先され、環境変数は参照されない。CLI と環境変数の両方がなければ、前節のビルド依存 fallback が使われる（同 `:1511,1661-1671,1708-1712`）。
- `HY4_EMBED_KERNELS` はこの環境変数を読む条件ではなく、unset 時に埋め込みカーネルを候補にするかを決める build macro。`build_mac.sh` は `-DHY4_EMBED_KERNELS` を付け、`build_vis.sh` は付けずに同じ `hy4_metal_main.cpp` をビルドする（`engine/src/hy4flash/metal/build_mac.sh:43-47`; `engine/src/hy4flash/metal/build_vis.sh:18-20`; `engine/src/hy4flash/metal/hy4_metal_main.cpp:1400-1433`）。
- `--image` を使う場合も、選ばれた `kernels` の親ディレクトリが Vision カーネルの `hy4_mpp.metal` と `hy4_vision.metal` の探索元になる。そのため、この変数は画像処理を行う offline / serve 経路でも使われる（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1773-1780`; `engine/src/hy4flash/metal/hy4_metal_serve.h:365-370`; `engine/src/hy4flash/metal/hy4_metal_vision.h:91-102`）。
- MPP カーネルが利用可能かどうかは `Runner::init` 内の compile 成否で別に判定される。環境変数自体は MPP の有効・無効を切り替えず、指定されたパスからの compile を通じて間接的に利用可能性に影響する（`engine/src/hy4flash/metal/hy4_metal_main.cpp:523-556`）。

## 実行時の詳細

`main` が CLI 引数を読み終え、モデルをロードした後、serve では `hy4_serve_main` を呼ぶ直前に、offline では token 読み込み後に、この値を最大 1 回読み取る。serve では `kernels` が空のときだけ読み、offline も `kernels` が空のときだけ読む。読み取った値はローカル変数 `kernels` に保持して初期化へ渡され、リクエストごとの再読込やプロセス内キャッシュはない（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1488-1512,1615-1674,1676-1720`）。

serve の初期化は `Runner::init` に入り、指定パスと同じディレクトリの HY4 Metal ソース群を compile する。`--image` がある場合は同じディレクトリから Vision カーネルも compile する（`engine/src/hy4flash/metal/hy4_metal_serve.h:219-243,365-370`; `engine/src/hy4flash/metal/hy4_metal_main.cpp:523-556`; `engine/src/hy4flash/metal/hy4_metal_vision.h:91-102`）。

環境変数が空文字または誤ったパスでも、環境変数選択時点では検証・警告されない。後続の compile が失敗すると、`Runner::init` の通常カーネル compile は `mtl::Context::compile` に入り、stderr に `mtl: compile failed (...)` を出して終了コード `3` でプロセスを終了する。MPP compile の試行失敗は fallback して通常カーネル compile を試す。初期化が false を返す別の失敗は offline で stderr の `init: <理由>` と終了コード `1`、serve ではプロトコル出力 `ERR init: <理由>` と終了コード `1` になる（`engine/metal/src/mtl_rt.mm:170-179`; `engine/src/hy4flash/metal/hy4_metal_main.cpp:533-556,1762-1765`; `engine/src/hy4flash/metal/hy4_metal_serve.h:239-243`）。

## ログと測定値

この環境変数を読んだことや、その値を採用したことを示す専用ログはない。存在しないパスなどの問題はカーネル compile 時に現れ、上記の `mtl: compile failed (...)` 等の経路に進む（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1661-1674,1708-1720`; `engine/metal/src/mtl_rt.mm:170-179`）。この変数による性能測定値は、対象資料に記載がない。

## 根拠

- 全参照と値の選択: `engine/src/hy4flash/metal/hy4_metal_main.cpp:1661-1674,1708-1720`。
- CLI 優先順位・早期終了・モデルロード後の読み取り時期: 同 `:1511,1575-1588,1615-1637`。
- 埋め込み macro と build 経路: 同 `:1400-1433`; `engine/src/hy4flash/metal/build_mac.sh:43-47`; `engine/src/hy4flash/metal/build_vis.sh:18-20`。
- カーネル compile と失敗時の処理: `engine/src/hy4flash/metal/hy4_metal_main.cpp:523-556,1762-1765`; `engine/src/hy4flash/metal/hy4_metal_serve.h:219-243`; `engine/metal/src/mtl_rt.mm:170-179`。
- Vision カーネルの探索元: `engine/src/hy4flash/metal/hy4_metal_main.cpp:1773-1780`; `engine/src/hy4flash/metal/hy4_metal_serve.h:365-370`; `engine/src/hy4flash/metal/hy4_metal_vision.h:91-102`。

索引 `docs/envvars/000_envvers.md` のレジストリ項目は `backends: [cuda-hip]` と記載しているが、実際に読み取る両箇所は `engine/src/hy4flash/metal/hy4_metal_main.cpp` にある。索引はこの作業では変更していない。
