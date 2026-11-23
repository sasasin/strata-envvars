# `strata-hy4-metal --dfly-override`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal`（Metal） |
| オプション | `--dfly-override` |
| 別名 | なし |
| 値 | ファイルパスを1つ取る。パス形式の検証はない |

## 役割

Hy4-Flash Metal runner が読む DFly tensor の一部を、指定した flat override ファイルの内容で差し替える。対象名は `model.dfly_layers.*` に限られる。override はモデルファイルを書き換えず、runner が tensor を参照する際に指定ファイル内のデータを使う。

## 使い方

```sh
strata-hy4-metal --model SQ64.strata --dfly-override ./dfly-override.bin --tokens ids.txt --gen 32
```

override ファイルは `DFLYOVR1` 形式で用意する。モデルなど通常の実行引数も指定する。

## 値と既定値

- `--dfly-override` の直後の argv 文字列をパスとして受け取り、既定値は空（未指定）である。空文字列の場合も override 読み込みを行わない。
- 同じ引数が複数回あれば、変数への代入が繰り返されるため最後のパスが使われる。
- Metal loader が受理するファイルは、最低16 byteで先頭8 byteが `DFLYOVR1` のもの。bytes 8–11 を entry 数として読み、entry は offset 16 から始まる。各 entry は `uint32` 名長、`uint64` payload offset、`uint64` byte 長、8 byte 境界に詰めた tensor 名で構成される。payload offset はファイル先頭からの位置として使われる。
- CLI 側に値の追加検証はない。loader は entry header・名前領域・payload がファイル範囲内か、tensor 名が `model.dfly_layers.` で始まるか、モデル manifest に存在するか、manifest の byte 長と一致するかを検査する。

## 実行時の動作

runner はモデルをロードした後、通常の推論処理や `--load-only` の終了判定より前に override を読み込む。ファイル全体を読み取りモードで開き、サイズ分の Metal buffer を確保して読み込み、entry ごとの tensor 名と payload offset を記録する。該当する tensor が `tw()` / `tf()` 経由で参照されると、その buffer の payload を返し、override にない名前は元のモデル buffer から返す。従ってファイルは起動時に読み込まれ、モデルファイル自体への書き込みは行わない。

この指定自体は DFly 実行を有効化しない。推論時に対象 tensor が参照される経路でのみ差し替えが効果を持つ。たとえば `--draft off` や speculative mode の条件が成立しない実行では、override を読み込んでも DFly tensor が推論に使われない場合がある。Metal runner の speculative mode は、生成・benchmark の要求、draft が off でないこと、manifest に DFly tensor があること、chunk が16以上、all-logits でないこと、画像入力がないことなどで決まる。

## 適用条件と副作用

- 対象は `strata-hy4-metal` の Metal runner。CUDA/HIP および SYCL の実装・ファイル形式が同一であるとは、この文書では扱わない。
- override ファイルはモデルロード後に全体を Metal buffer へ読み込むため、そのファイルサイズ分の buffer を確保する。読み込みに GPU 実行は必要ないが、Metal context はモデルロード前に作成される。
- entry 名が同じものを複数含む場合、名前から offset への map には後の entry が残る。名前の重複を拒否する検査は確認できなかった。
- entry 数が0なら読み込み成功として診断を出すが、tensor の置換は起きない。
- オプション値を省略した場合の `nxt()` は argv 境界を検査せず次の argv を参照する実装である。値の省略時の安全なエラー処理は確認できなかった。

## 出力とエラー

- 読み込み成功時は stderr に `[dfly-override] loaded ...` を出す。
- ファイルを開けない、16 byte 未満、短い読み込み、magic 不一致、entry header / 名前 / payload の範囲外、非 DFly tensor 名、manifest にない tensor 名、tensor byte 長の不一致は読み込み失敗となる。stderr に `dfly-override: <理由>` を出し、終了コード1で終了する。
- 不明なフラグは stdout に `ERR unknown flag ...`、stderr に `unknown arg ...` を出して終了コード2となる。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1488-1506,1566` — Metal runner の argv parser。パスを文字列として受け取り、別名や値検証を設けていない。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:179-211` — ファイル読込、形式・entry・tensor 検証、成功診断。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1611-1627` — `--model` 必須確認、モデルロード後の override 適用と失敗時終了コード。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:299-313` — 置換対象名の tensor accessor と元モデルへの fallback。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1755-1762` — DFly tensor の有無および speculative mode の適用条件。
- `docs/cli/README.md:1358-1374`、`docs/cli/000_cli_tools.md:11` — `strata-hy4-metal` の parser 所在と `metal/` scope、索引上のリンク。
