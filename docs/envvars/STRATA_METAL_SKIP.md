# `STRATA_METAL_SKIP`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

Metal engine が実行する window の dispatch のうち、pipeline 名に指定した部分文字列を含むものを空の grid に置き換えます。コメント上も「timing only (WRONG answers)」とされており、カーネル群を抜いたときの時間を測るための診断用フックです。通常の推論設定として使う変数ではなく、設定すると結果は正しくありません。

対象実装は `metal/` の Metal engine です。`metal/CMakeLists.txt` は Metal ビルドを macOS 専用としており、CUDA/HIP/SYCL ビルドには含めないと記載しています。window の初期化はモデル形状を Qwen3.8-Flash-Next 用の定数と照合するため、この engine の対象モデル以外ではこの dispatch 経路に入りません。

## 値と判定

値を真偽値として parse せず、カンマ区切りの部分文字列リストとして読みます。

| 状態・値 | 判定と効果 |
|---|---|
| 未設定 | スキップ対象なし。 |
| 空文字 | 分割後の要素がないため、スキップ対象なし。 |
| `a,b` | `a` と `b` をそれぞれ部分文字列として照合する。どちらかを pipeline key に含む dispatch をスキップする。 |
| `a,,b,`、`,a` | 空の要素は追加されず、空要素による全 pipeline への一致は起きない。 |
| 空白を含む要素 | 空白を trim しない。たとえば `a, b` の2番目は先頭に空白を含む ` b` として照合する。 |

照合は `std::string::find` による大文字小文字を区別する部分文字列検索です。数値変換、正規表現、完全一致はありません。環境変数のリストは関数内の `static const` として初回 `push()` 時に一度だけ構築されるため、その後の環境変更は反映されません。

## 有効になる条件

- macOS 上で Metal engine をビルドし、その `Window` が dispatch を構築する経路でのみ参照されます。
- `Window::push()` を通る dispatch が対象です。同じ `window.cpp` 内でもこの関数を通らない処理や、Metal engine 外の backend には適用されません。
- リスト要素が pipeline key に部分一致しなければ何も変わりません。key は `Window::P()` が pipeline 作成時に登録します。

## 実行時の詳細

`push()` は dispatch の pipeline pointer から `pkey_of_` を引き、いずれかの要素が key に含まれると `d.indirect` を `nullptr` にし、`d.grid[0]` を `0` にします。その dispatch 自体はリスト `ds` に残り、graph に記録されますが、通常の直接 dispatch としてエンコードされる際の threadgroup 数が 0 になります。dispatch 数を減らす処理ではありません。

作成された dispatch 群は window shape ごとの `wcache_` に保存され、以降同じ shape の実行ではキャッシュを再利用して `run_ds()` から graph を実行します。したがって変数はリクエストごとに読み直されるものではなく、初回構築時に dispatch 群へ反映されます。値が空でない場合の専用ログやエラー終了はこのコードにはありません。スキップ対象のカーネルが必要とする計算も行われず、後続処理は不完全な中間値を使うため、生成結果の正しさは保証されません。

## 根拠

- `metal/src/engine/window.cpp:148-154` — `P()` が pipeline key を登録。
- `metal/src/engine/window.cpp:156-175` — 初回の環境変数読み取り、カンマ分割、部分一致、dispatch の grid 変更とリストへの追加。
- `metal/src/engine/window.cpp:950-1022,1088-1098` — window shape ごとの dispatch cache と graph 実行。
- `metal/CMakeLists.txt:1-18,70-75` — Metal 部分が macOS 専用であり、CUDA/HIP/SYCL ビルドに含まれないこと、および engine のビルド条件。
- `metal/src/mtl_rt.mm:208-225` — `indirect == nullptr` のとき `grid` を使って直接 dispatch する実装。

`docs/` 内に `STRATA_METAL_SKIP` の個別説明は見つかりませんでした。挙動の根拠は上記の実装です。
