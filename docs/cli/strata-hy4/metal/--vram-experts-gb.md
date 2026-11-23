# `--vram-experts-gb`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal` |
| オプション | `--vram-experts-gb` |
| 別名 | なし |
| 値 | 引数を1つ取る。Metal runner は値を数値変換せず、VRAM上限にも使用しない |

## 役割

Metal runner はこのフラグを互換目的で受け取り、値を読み飛ばして未使用の警告を出します。したがって、このオプションでMetal上のexpert用VRAM容量を指定することはできません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1603`）。

## 使い方

```sh
# 受理されるが、8.0 はMetal runnerのVRAM割り当てに反映されない
strata-hy4-metal --model model.strata --tokens prompt.ids --vram-experts-gb 8.0
```

## 値と既定値

オプション分岐は次の `argv` 要素を1つ読み取り、その文字列を警告に表示します。数値変換、範囲検証、設定値への保存はありません。値を省略した場合の明示的なエラー処理もなく、`nxt` は `argv[++i]` をそのまま `std::string` に渡します。そのため値は省略せず指定してください。数値の既定値や有効範囲はMetal runnerには定義されていません（同ファイル `:1506`, `:1603`）。

## 実行時の動作

引数解析中に `--vram-experts-gb` を見つけると、直後の引数を消費して `[args] --vram-experts-gb <値>: not used by the Metal runner` を標準エラーへ出力し、引数解析を続けます。この分岐からVRAM予算を設定する処理には進みません。Metal実装内での参照箇所もこの未使用警告の分岐だけです（同ファイル `:1506`, `:1603`）。

## 適用条件と副作用

この分岐は `strata-hy4-metal` の引数解析で動作します。値はVRAM上限に影響しません。副作用は未使用警告の標準エラー出力です。引数を1つ消費するため、値を省略すると後続のフラグを値として消費する形になりますが、末尾で値を省略した場合の安全な処理は実装されていません（同ファイル `:1506`, `:1603`）。

## 出力とエラー

値を指定すると、stderr に `[args] --vram-experts-gb <値>: not used by the Metal runner` が出ます。この警告自体では処理を終了せず、その後の通常の必須引数確認・モデル読み込みへ進みます（同ファイル `:1603-1622`）。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1506` — `nxt` は次の引数を `argv[++i]` から取得する。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1603` — `--vram-experts-gb` を含むGPU向け引数を値付きで受理し、Metal runnerでは使わない旨をstderrに出す。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1604-1622` — 未知フラグは終了コード2、モデル未指定はusageを出して終了コード2、モデル読み込み失敗はエラーを出して終了コード1。未使用警告の分岐は終了せず処理を続ける。
- `docs/cli/README.md:1358-1449` — `strata-hy4-metal` のscopeと、作成対象リンクが `strata-hy4/metal/--vram-experts-gb.md` であることを確認。

調査時の Strata checkout は `## main...origin/main` で、`git status --short --branch` に未コミット変更は表示されませんでした。
