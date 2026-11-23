# `strata-inkling-metal --no-warm`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling-metal`（Metal） |
| オプション | `--no-warm` |
| 別名 | なし |
| 値 | 値なしのフラグ |

## 役割

モデル読み込み後に実行するページ事前ウォームアップを省略します。通常はモデルファイルの mmap 領域を先読みし、初回 decode 時の cold page fault による停止を避ける目的で実行されます。

## 使い方

```sh
strata-inkling-metal --model ./model.strata --no-warm
```

`--model` には使用する `.strata` モデルファイルを指定します。

## 値と既定値

値は取りません。`--no-warm` を指定すると `do_warm` が `false` になります。省略時は `do_warm = true` であり、ウォームアップが有効です。引数 parser は同じフラグの複数指定を拒否せず、いずれも `false` を設定します。フラグに値を続ける構文はありません。その値相当の文字列は次の引数として処理され、未知の引数として終了します。

## 実行時の動作

通常経路では、モデルの `load()` が完了した後、Metal runner の初期化より前に `do_warm` が真なら `mod.warm(8)` を呼びます。`--no-warm` はこの呼び出しだけをスキップします。モデル自体のロード、runner 初期化、後続モードの処理は引き続き行われます。

`warm()` はモデルファイル全体の mmap 領域に `madvise(..., MADV_WILLNEED)` を呼び、8スレッドを起動して16 KiB単位のページを読み取ります。`--no-warm` によりこの先読みとページ接触を省きます。初回アクセス時のページフォールトや実行時間がどう変わるかは、ここでは測定していません。

## 適用条件と副作用

オプションは Metal 版 `strata-inkling-metal` の parser に定義されています。`--version` と `--info` は parser 中で即時 return するため、これらの早期終了経路ではモデル読み込みやウォームアップに到達しません。通常経路では、`--selfcheck`、`--spec-check`、`--bench`、`--par-sweep` など後続モードの選択にかかわらず、runner 初期化前のウォームアップ判定に適用されます。

このフラグ自体の出力やファイル変更はありません。ウォームアップを省くことで初回のモデルページアクセスが遅延し得ますが、実際の影響量はソースからは判断できません。

## 出力とエラー

`--no-warm` 固有の診断出力や失敗経路はありません。値を付けた場合など parser が認識しない引数は `unknown arg: ...` を stderr に出し、終了コード `2` で終了します。モデル load と runner 初期化はこのオプションの有無にかかわらず実行され、失敗時はそれぞれ `[ERROR] load: ...`、`[ERROR] runner init: ...` を stderr に出して終了コード `1` となります。

## 根拠

- `engine/src/inkling2/metal/ink_metal_main.cpp:417-430` — CLI 状態の初期値。`do_warm` は既定で `true`。
- `engine/src/inkling2/metal/ink_metal_main.cpp:432-468` — 引数 parser。`--no-warm` は値なしで `do_warm = false` にし、未知の引数は stderr と終了コード `2`。
- `engine/src/inkling2/metal/ink_metal_main.cpp:438-443` — `--version` と `--info` の早期終了。
- `engine/src/inkling2/metal/ink_metal_main.cpp:470-493` — モデル指定の確認、load、ウォームアップ呼び出し、runner 初期化の順序と失敗出力。
- `engine/src/inkling2/metal/ink_metal_main.cpp:517-616` — ウォームアップ後に実行される selfcheck、spec-check、bench、par-sweep 等。
- `engine/src/inkling2/metal/ink_metal_common.h:356-371,448-456` — モデルファイルの mmap とファイルサイズの設定。
- `engine/src/inkling2/metal/ink_metal_common.h:829-848` — `warm()` の目的、`madvise(MADV_WILLNEED)`、8スレッドでの16 KiBページ読み取り。
