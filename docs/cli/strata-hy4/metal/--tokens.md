# `strata-hy4-metal --tokens`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal`（Metal） |
| オプション | `--tokens` |
| 別名 | なし |
| 値 | トークン ID を空白区切りで記したファイルのパス |

## 役割

Metal 版 Hy4-Flash のオフライン実行で、事前にトークン化した入力列をファイルから読み込み、prefill の入力にします。生成する場合の追加トークン数は別の `--gen` で指定します。`--serve` ではサーバー起動経路へ分岐してこのファイルを読み込まず、`--load-only` でもモデル読込後に終了するため読み込みません。

## 使い方

```sh
# prompt.ids に空白区切りでトークン ID を記した入力を使い、Metal でオフライン実行する
strata-hy4-metal --model model.strata --tokens prompt.ids
```

追加生成を行う場合は `--gen` を併用します。

```sh
strata-hy4-metal --model model.strata --tokens prompt.ids --gen 32
```

## 値と既定値

- `--tokens` の後の次の引数をファイルパスとして受け取ります。短縮別名はありません。parser は `tok_path` に値を代入し、同じオプションを複数回指定した場合は最後のパスが残ります（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1488-1509`）。
- パスの既定値は空文字列です。ファイル内容は `long` としてストリーム抽出し、読み取れた数値を `int32_t` に変換して列へ追加します。数値の範囲確認やファイルを開けたかの個別確認はありません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1676-1681`）。
- 空ファイル、開けないファイル、または先頭から数値を読み取れないファイルでは列が空のままとなり、通常のオフライン経路では `no tokens` と stderr に出して終了コード 2 になります（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1701-1705`）。途中に数値でない内容がある場合はストリーム抽出がそこで止まり、それまで読めた数値だけが使われます。個別の形式エラーは出しません（同 `:1678-1680`）。
- オプション値の省略を検出する専用チェックはありません。値取得は `argv[++i]` で行われます（同 `:1504-1509`）。

## 実行時の動作

オフライン経路ではファイルから読み取った ID 列を `tok` とし、その要素数を入力長 `T0` にします。必要なら `--image` による画像 pad 展開を行った後、`T0` が 0 でなければその列を chunk に分けてモデルの prefill に渡します（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1676-1705,1784-1812`）。`--gen` が正数なら prefill 後に生成処理を行い、生成 ID を `gen_ids.txt` に書き込みます。通常経路では prefill の top-5 結果を `top5.txt` に書き込みます（同 `:1818-1845,1944-1980`）。

`--ctx` を正数で指定しない場合、コンテキスト長は `T0 + gen + 16` になります。`--all-logits` は最終 prefill chunk の全位置の logits を対象にし、`--dump` または `--save-logits` が指定されている場合は logits を `--out` 配下の `logits.npy` に保存します（同 `:1701-1707,1802-1808`）。

## 適用条件と副作用

- 索引上の対象は Metal 実装の `strata-hy4-metal` です。索引は `strata-hy4/metal/--tokens.md` にこのオプションを掲載しています（`docs/cli/README.md:1358-1361,1443`）。
- 通常のオフライン実行では読み込んだ ID 列がモデル推論に渡されます。`--serve` はモデル読込後にサーバー処理へ戻るため `--tokens` は参照されず、`--load-only` はその前に終了します（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1515,1635-1675`）。
- ファイルの内容は入力として読み取るだけです。生成や logits などの出力ファイルは `--tokens` 自体ではなく、実行経路や `--gen`、`--dump`、`--save-logits` 等の条件で作られます（同 `:1802-1808,1944-1980`）。
- ID がモデル語彙の範囲内かをこの parser／読込箇所で検査する処理は確認できません。後段の全ての値に対する挙動はここから断定しません。

## 出力とエラー

- 入力列が空の場合、stderr に `no tokens` を出して終了コード 2（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1701-1705`）。
- ファイルを開けない場合も読込エラー自体は出さず、通常は空列として上記の経路になります（同 `:1676-1680,1701-1705`）。
- 入力列がある場合、prefill の進捗・統計は stderr、top-5 結果は stdout に出力され、通常経路では `top5.txt` にも書かれます（同 `:1812-1817,1978-1980`）。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1488-1509` — Metal runner の parser。`--tokens` は次引数をパスとして保存し、別名はない。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1635-1675` — `--load-only` と `--serve` の早期分岐。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1676-1707` — ファイル読込、空列エラー、既定コンテキスト長。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1784-1817,1944-1980` — prompt prefill、logits・生成・出力処理。
- `docs/cli/README.md:1358-1361,1443` — tool ID、Metal parser の識別、索引リンクと scope。
