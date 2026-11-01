# `STRATA_METAL_KERNELS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Metal runtime が実行時にコンパイルする `.metal` カーネルソースのディレクトリを指定します。`mtl::Context` が作られるときに値を読み、その Context で相対ファイル名のカーネルを読むときの基点にします。Metal 以外の backend ではこのコードはビルド対象ではありません。

## 値と判定

値はパス文字列としてそのまま使います。数値変換、空白除去、範囲検査、存在確認は環境変数の値に対して行いません。

| 状態 | 選択されるパス |
|---|---|
| 未設定 | 実行ファイルの隣に `metal/kernels` があればそのパス。なければビルド時に埋め込まれた `metal/kernels` のパス |
| 設定済みで空文字 | 空文字をそのまま採用。fallback しない |
| 設定済みで非空 | 文字列をそのまま採用。相対パスはプロセスの作業ディレクトリ基準で使われる |

カーネル名が絶対パスならそのまま読み、相対名なら選択したディレクトリに `/` と名前を連結します。したがって空文字の場合、相対名 `quant.metal` は `/quant.metal` になります。パスとして妥当かは選択時には検証されません。

## 有効になる条件

- `metal/CMakeLists.txt` は `APPLE` 以外で configure を停止し、この変数を読む `mtl_rt.mm` と Metal エンジンに使うビルド定義を設定します。
- Metal エンジンが `mtl::Context` を生成した場合に読み取ります。Qwen 系 `strata` の Window と DS4 runtime の Context 生成経路があります。
- CLI 引数や別の Strata 環境変数との優先順位はありません。設定済みなら、実行ファイル隣の配布用フォルダーとコンパイル時パスの両方より優先されます。

## 実行時の詳細

`Context` のコンストラクターで `strata_metal::resource("STRATA_METAL_KERNELS", "kernels", STRATA_METAL_KERNELS_DEFAULT)` を呼びます。helper は環境変数が未設定でない限り値を即座に返し、未設定時だけ `<実行ファイルのディレクトリ>/metal/kernels` の存在を調べ、その後ビルド時パスに fallback します。選択値は Context の `kernel_dir` フィールドに保存されます。環境変数は Context ごとに構築時に再評価され、保存後にプロセス環境を変更しても既存 Context の値は変わりません。

`Context::compile()` は相対ファイル名を `kernel_dir + "/" + ファイル名` にして読みます。ファイルが開けない場合は stderr に `mtl: cannot read <path>` を出して終了コード 2 で終了します。読み込みに成功しても Metal ソースのコンパイルに失敗すると、別経路で `mtl: compile failed (...)` を出し、終了コード 3 で終了します。これは Strata の読み込み・エラー処理です。Metal driver/compiler の内部動作はこの変数の説明対象に含めません。

## 根拠

- 変数名候補: `000_envvers.md:1044`（候補一覧であり、実装根拠ではない）。ソース全体の完全一致検索では、読み取り呼び出し以外に helper の説明コメントと CMake の既定値定義が見つかりました。
- Apple 専用ビルドと実行時カーネルの構成: `metal/CMakeLists.txt:1-18,32-39,121-130,155-159`。
- 環境変数を動的に受け取る helper、未設定時の fallback、値の優先順位: `metal/src/resource_path.h:13-14,25-54`。
- Context ごとの選択と保存: `metal/src/mtl_rt.mm:292-316`、フィールド定義 `metal/src/mtl_rt.h:138-139`。Qwen Window の生成位置は `metal/src/engine/window.cpp:542`、DS4 Context の生成例は `metal/src/engine/ds4_ctx.cpp:34-35`。
- 相対名の解決、ファイル読み込み、失敗時の stderr と終了コード: `metal/src/mtl_rt.mm:32-41,331-341`。Metal ソースのコンパイル失敗経路: `metal/src/mtl_rt.mm:352-359`。
