# `STRATA_METAL_SKIP`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Metal エンジンが `Window::push` で登録する dispatch のうち、pipeline key に指定文字列を含むものを空の grid にして実行しない、診断・時間比較用のフックです。実装コメントも「timing only (WRONG answers)」と明記しています。通常の推論設定ではなく、該当 dispatch の計算を飛ばして後続を走らせるため、結果の正しさは保たれません。`engine/metal/src/engine/window.cpp:335-354`

この処理は `STRATA_GPU_METAL` ビルドで Verify から Metal decode window に引き渡す実装にあります。したがって Metal window を使う経路に限られ、CUDA/HIP/SYCL の dispatch には適用されません。CMake では Metal エンジンを `strata_metal_kernels` として組み込み、`strata` 実行ファイルをリンクします。`engine/src/core/verify.cpp:99-107` `engine/metal/CMakeLists.txt:150-177`

## 値と判定

`std::getenv` で値を読み、カンマで分割した各非空文字列を `std::string::find` に渡して pipeline key の部分文字列検索をします。bool・数値への変換やトリミングはありません。大文字小文字を区別します。空文字列と空のトークンは捨てられ、空の一覧なら何もスキップしません。`engine/metal/src/engine/window.cpp:340-352`

| 条件 | unset | 一致して dispatch が無効になる例 | 一致しない例 |
|---|---|---|---|
| Metal `Window::push` | スキップ一覧が空 | `gemv` は pipeline key `gemv` に一致。`a,b` は `a` または `b` を含む key に一致 | 空文字、`,,` は一覧が空。` GEMV`（先頭空白付き）は `gemv` と一致しない。大文字小文字も区別する |

各 comma 区切り要素は空なら追加されませんが、前後の空白はそのまま検索文字列に残ります。`0`、`1`、`true`、`false`、`0anything` も特別な真偽値ではなく、通常の部分一致文字列です。そのため、たとえば `0` は key に文字 `0` があれば一致し、なければ一致しません。`a,,b,` は `a` と `b` の 2 要素として扱われます。`engine/metal/src/engine/window.cpp:342-351`

## 有効になる条件

- `STRATA_GPU_METAL` を定義した Metal ビルドで、Metal `Window` の `push` 経由で dispatch を構築すること。Verify はこの macro の分岐で Metal window を生成・初期化します。`engine/src/core/verify.cpp:99-107,978-985`
- 指定した文字列が `P()` に渡され `pkey_of_` に登録された key の一部と一致すること。検索対象は kernel 関数名そのものではなく、この pipeline key です。key は `P()` で pipeline 作成時に記録されます。`engine/metal/src/engine/window.cpp:327-333,348-351`
- prompt chain は `Window::push` を通さず dispatch を直接追加する別経路です。その経路の dispatch にはこの変数の部分一致処理はかかりません。`engine/metal/src/engine/prompt_chain.inc:1-10,490-508,541-557`
- この変数を CLI 引数、設定ファイル、他の環境変数で有効化・上書きする分岐はありません。Metal window の `push` が呼ばれない実行経路では効果がありません。

## 実行時の詳細

関数内 `static const` の一覧として、プロセス中で最初に `Window::push` が呼ばれた時に一度だけ評価されます。その時点で未設定または空なら、同じプロセス内で後から環境を変更しても再読込されません。設定値は各 dispatch 追加時に使われ、dispatch の key にいずれかの要素が含まれると `d.indirect` を `nullptr` にし、`d.grid[0]` を `0` にします。`engine/metal/src/engine/window.cpp:335-354`

`push` は dispatch を一覧に追加する前に `mtl::require_fit` を呼びますが、これは threadgroup の thread 数を検査します。skip 処理が変えるのは grid の x であり threadgroup のサイズではありません。実行時の encoder は indirect grid がない場合も含め `d.grid` を渡して dispatch を encode します。window 実行後も通常どおり後続処理・出力処理に進むため、スキップされた計算の結果を後段が読む可能性があります。`engine/metal/src/engine/window.cpp:349-354,1632-1641` `engine/metal/src/mtl_rt.mm:414-434`

## ログと測定値

この変数を読み取る箇所には、有効・無効を知らせるログや専用エラー出力はありません。Metal window の通常実行はそのまま進みます。ソースコメントはこのフックを timing 用とし、答えが誤ると明記しています。スキップ時の数値的な差や測定値は、この checkout の資料からは確認できません。`engine/metal/src/engine/window.cpp:338-354,1637-1641`

## 根拠

- 候補一覧には `STRATA_METAL_SKIP` が記載されていますが、実際の Strata 所有ソースの読み取りは `engine/metal/src/engine/window.cpp:342` のみです。全参照検索では同じファイルのコメントと `terminal/data/settings-register.json` の登録データも見つかりました。後者は環境から値を読む実装ではありません。
- `engine/metal/src/engine/window.cpp:327-354` — pipeline key の登録、値の一度限りの読み取り、分割、部分一致、grid の変更、dispatch 登録。
- `engine/src/core/verify.cpp:99-107,978-985` — `STRATA_GPU_METAL` 分岐と Metal window 初期化。
- `engine/metal/src/engine/prompt_chain.inc:490-508,556-557` — prompt chain の直接 dispatch 登録と実行。
- `engine/metal/src/mtl_rt.h:58-77`、`engine/metal/src/mtl_rt.mm:414-434` — dispatch grid と実行時 encode。
