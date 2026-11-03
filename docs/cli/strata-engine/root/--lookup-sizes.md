# `--lookup-sizes`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジンの root 引数） |
| オプション | `--lookup-sizes` |
| 別名 | なし |
| 値 | カンマ区切りの整数列。各値は許可する prompt-lookup 検証 window の token 数候補 |

## 役割

`--lookup-max-t` が有効なとき、MTP が使う window サイズに加えて、prompt lookup が使用可能な window サイズを指定します。指定したサイズは候補の許可リストになり、実行時にその全サイズが毎回使われるわけではありません。ドラフト方針が候補から選びます（`src/program/generate.cpp:1303-1321`、`include/strata/spec/draft_policy.hpp:41-44,82-89`）。

## 使い方

```sh
strata --serve --pack ./model.strata --lookup-max-t 12 --lookup-sizes 6,8,12
```

この例では、MTP のサイズ群は残したまま、prompt lookup の追加候補を 6、8、12 token に制限します。`--lookup-max-t` も指定しないと、`--lookup-sizes` のリストはサイズ許可マスクに反映されません。

## 値と既定値

- 値は必須です。値の文字列はそのまま保存され、parser では数値形式や範囲を検証しません（`src/program/generate.cpp:3295-3298,3551-3553`）。値を省略すると `--lookup-sizes needs a value` を stderr に出し、終了コード 2 で終了します（同 `:3295-3297`）。
- オプション自体の既定値は空文字列です（`src/program/generate.cpp:978-979`）。`--lookup-max-t` が有効で、かつ値が空でない場合、カンマ区切り各要素を `atoi` で整数化し、2 以上 `--spec` 以下だけを候補に加えます。範囲外の値は無視され、重複値は同じ bit になるため一つにまとまります（同 `:1303-1321`）。
- `atoi` による変換なので、厳密な整数列 validation はありません。例えば数値に変換できない要素は 0 相当となり候補から除外され、数値部分の後ろに文字がある要素も数値部分として扱われ得ます。空要素も別途エラーにはなりません（同 `:1312-1318`）。
- 未指定（空文字列）の場合は、MTP の最大サイズ `s_mtp` より大きいサイズのうち `s_mtp+1`、`s_mtp+2`、`--spec` 以下のものが候補になります（同 `:1305-1310`）。

## 実行時の動作

`--lookup-max-t <= 0` の場合、サイズ許可関数は全サイズを許可するマスクを返すため、このオプションの値は使われません（`src/program/generate.cpp:1303-1305`）。有効な場合、まず MTP 側のサイズ 1 から `s_mtp` までを常に許可し、指定リストに該当するサイズを追加します。`s_mtp` は `--mtp-max-t` が正なら `min(--mtp-max-t, --spec)`、それ以外は `--spec` です（同 `:1305-1319`）。したがって、このリストは MTP サイズを無効化せず、prompt lookup の追加サイズを絞ります。

`--lookup-max-t` が正で `--suffix-draft` も有効、かつ `--spec >= 2` のとき、エンジンは `--spec` を lookup の上限に合わせて拡張します（上限は `kVerifyLongT`）。lookup サイズ候補のマスクは serve と通常 generate の両方のドラフト方針に設定されます（同 `:4156-4159,13417,20031`）。方針は候補サイズと lookup 提案を考慮して選択します（`include/strata/spec/draft_policy.hpp:41-44,82-89`）。

## 適用条件と副作用

- `--lookup-max-t` が無効または 0 以下なら `--lookup-sizes` は実質無視されます。自動で `--lookup-max-t` が 12 になる条件は別途定められています。8-row の narrow-window build、非 Metal、serve、単一 GPU、layer split なし、batch なし、DFlash2 なし、lookup-chain なし、suffix-draft 有効、`--spec >= 2` で、かつ `STRATA_LOOKUP_MAX_T` が `0` で始まらない場合です。それ以外は自動値 0 です（`include/strata/core/lookup_default.hpp:9-27`、`src/program/generate.cpp:4143-4154`）。
- 候補 window ごとに CUDA graph が必要で、ソースコメントは graph あたり約 20–35 MiB の VRAM と説明しています（`src/program/generate.cpp:972-976`）。serve 経路では window graph の準備時に VRAM 不足となったサイズを候補から削除し、より小さい許可サイズへフォールバックします。VRAM 不足以外の準備失敗は `ERR <理由>` を stdout に出して終了コード 1 になります（同 `:13423-13437,18237-18240`）。
- layer split の serve では許可マスクを narrow window の範囲に制限します（同 `:13417-13419`）。またソースの help は `--lookup-sizes` を `--lookup-max-t` と併用する値として説明しています（同 `:1143-1145`）。

## 出力とエラー

serve 経路で `--lookup-max-t > 0` の場合、stderr に有効な lookup 上限と候補サイズを表示します。VRAM 不足で graph の capture に失敗すると、そのサイズを落とした旨と残り候補を stderr に出し、より小さい候補へ進みます（`src/program/generate.cpp:13420-13435`）。値そのものに対する専用の拒否メッセージはなく、変換後に 2..`--spec` の範囲外となる要素は黙って無視されます（同 `:1312-1318`）。

## 根拠

- parser と値取得: `src/program/generate.cpp:3295-3298,3551-3553`
- option の保存先と用途コメント: `src/program/generate.cpp:972-979`
- サイズ文字列の変換と許可マスク: `src/program/generate.cpp:1300-1321`
- `--lookup-max-t` の適用、自動既定値、`--spec` との連動: `src/program/generate.cpp:4140-4159`、`include/strata/core/lookup_default.hpp:9-27`
- serve / generate の方針への適用、serve の VRAM fallback: `src/program/generate.cpp:13417-13437,18237-18240,20031`
- 候補サイズの意味と方針 API: `include/strata/spec/draft_policy.hpp:17-19,41-44,82-89`、`src/spec/draft_policy.cpp:31-43`
- 補助資料: `src/program/generate.cpp:1143-1145` の組み込み help。リポジトリ内の概要は `docs/DETAILS.md:1086`。

調査範囲はこの commit の checkout 内ソースと同梱 help・`docs/DETAILS.md` です。Release 配布物や各 backend の実行時挙動は別途確認していません。
