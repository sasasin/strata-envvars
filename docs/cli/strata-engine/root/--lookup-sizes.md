# `--lookup-sizes`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数） |
| オプション | `--lookup-sizes` |
| 別名 | なし |
| 値 | カンマ区切りの window サイズ（整数として読み取られ、`2..--spec` の範囲だけ有効） |

## 役割

`--lookup-max-t` による prompt-lookup の候補サイズを指定します。MTP が担当するサイズは引き続き候補に含まれ、このオプションはそれより大きい lookup window の候補を制限します。`--lookup-max-t` が 0 以下の場合、この値はサイズ選択に使われません（`engine/src/program/generate.cpp:1508-1525`）。

## 使い方

```sh
strata --pack MODEL --serve --spec 8 --mtp-max-t 4 --lookup-max-t 8 --lookup-sizes 5,6,8
```

この例では MTP の上限を 4、検証 window の上限を 8 とし、追加の lookup 候補を 5・6・8 にします。実際に使われるサイズは draft policy が選択し、VRAM に収まらないサイズは serve 実行中に除外される場合があります（`engine/src/program/generate.cpp:1508-1525`, `engine/src/program/generate.cpp:16406-16426`）。

## 値と既定値

- 値は必須です。省略すると parser が `--lookup-sizes needs a value` を stderr に出して終了コード 2 で終了します（`engine/src/program/generate.cpp:3839-3842`）。
- 既定値は空文字列です。`--lookup-max-t N` が有効で値が空なら、`MTP上限+1`、`MTP上限+2`、`--spec` のうち `--spec` 以下のサイズが候補になります（`engine/src/program/generate.cpp:1172-1173`, `engine/src/program/generate.cpp:1513-1517`）。
- 明示した各値は `atoi` で整数化され、2 以上かつ `--spec` 以下のものだけ候補に加わります。範囲外・数値でない要素はエラーにならず無視されます。重複値はビットマスクにまとめられます（`engine/src/program/generate.cpp:1518-1525`）。
- 厳密な数値形式検査はありません。したがって、数値の後ろに余分な文字がある要素も `atoi` が読める数値部分で扱われます。複数回指定すると `Options::lookup_sizes` を後の値で置き換えます（`engine/src/program/generate.cpp:4118-4119`）。
- `--lookup-max-t` が 0 以下なら `lookup_size_mask` は全サイズのビットを返し、`--lookup-sizes` の内容はサイズ制限として反映されません（`engine/src/program/generate.cpp:1508-1509`）。

## 実行時の動作

parser は値を文字列として `Options::lookup_sizes` に格納します（`engine/src/program/generate.cpp:1172-1173`, `engine/src/program/generate.cpp:4118-4119`）。後段の `lookup_size_mask` が、MTP 側のサイズを含む候補ビットマスクを作成します。`--mtp-max-t` が正なら MTP 上限は `min(--mtp-max-t, --spec)`、0 なら `--spec` です。明示値は MTP 上限より上のサイズを追加します（`engine/src/program/generate.cpp:1510-1525`）。

このマスクは serve と通常の生成処理の draft policy に渡され、MTP または prompt-lookup が使える window サイズを制限します（`engine/src/program/generate.cpp:16323`, `engine/src/program/generate.cpp:24791`）。ただし `--lookup-max-t` が未指定の場合は、serve・backend・GPU 数などから `default_lookup_max_t` が決まるため、明示的に指定しなくてもこのオプションが有効になる構成があります（`engine/src/program/generate.cpp:5038-5050`）。

## 適用条件と副作用

- `--lookup-max-t` が正のときだけ指定サイズによる制限が有効です。`--spec` が上限を決め、サイズ上限は検証 window の上限以下に収まる必要があります（`engine/src/program/generate.cpp:1518-1525`, `engine/src/program/generate.cpp:5051-5069`）。
- layer split では policy の候補サイズが narrow window 上限にさらに制限されます。また serve は layer split の window が上限を超える場合、stderr に制限を通知して `o.spec` を narrow window 上限に下げます（`engine/src/program/generate.cpp:13179-13184`, `engine/src/program/generate.cpp:16323-16326`）。
- serve は候補 window の graph を準備します。サイズごとに GPU メモリを使い、VRAM 不足のサイズは候補から除外して次の小さいサイズへ進みます。通常の decode/prompt 経路では、その旨と残るサイズを stderr に出します（`engine/src/program/generate.cpp:16410-16426`, `engine/src/program/generate.cpp:20326-20331`, `engine/src/program/generate.cpp:22631-22635`）。
- graph 準備が VRAM 不足以外の理由で失敗すると、該当する serve 経路は `ERR <理由>` を stdout に出して終了コード 1 を返します（`engine/src/program/generate.cpp:16414-16426`, `engine/src/program/generate.cpp:22631-22635`）。

## 出力とエラー

serve では `--lookup-max-t` が正の場合、MTP window 上限と現在の window サイズ一覧を stderr に表示します（`engine/src/program/generate.cpp:16406-16409`）。VRAM 不足でサイズを落とすと、落としたサイズと残りの候補も stderr に表示します（`engine/src/program/generate.cpp:16410-16426`）。

`--lookup-sizes` 自体に対する範囲エラーや不正形式エラーは確認できません。候補がなくなる場合の policy の最終的な選択動作は、このオプション文書の範囲では追跡していません。

## 根拠

- `engine/src/program/generate.cpp:1172-1173` — option の保存先と空文字列の初期値。
- `engine/src/program/generate.cpp:3839-3842`, `engine/src/program/generate.cpp:4118-4119` — 値の取得、parser の代入と多重指定時の上書き。
- `engine/src/program/generate.cpp:1508-1525` — 有効条件、既定候補、明示値の整数変換と範囲。
- `engine/src/program/generate.cpp:5038-5069` — `--lookup-max-t` の既定決定と window 上限。
- `engine/src/program/generate.cpp:13179-13184`, `engine/src/program/generate.cpp:16323-16326`, `engine/src/program/generate.cpp:24791` — layer split 制限と policy への適用。
- `engine/src/program/generate.cpp:16406-16426`, `engine/src/program/generate.cpp:20326-20331`, `engine/src/program/generate.cpp:22631-22635` — 表示、graph 準備、VRAM 不足時の除外と失敗経路。
