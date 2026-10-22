# `STRATA_BATCH_GROUPS_NV_SERIAL`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

`--batch-groups` を省略したとき、2 GPU の layer split における複数 slot の自動グループ数を 1 にする既定動作を選びます。通常の自動設定は GPU stage 数以下のグループに slot を分け、stage 間で pipeline 実行します。この変数が有効な条件では、2 GPU の自動設定を serial window（1 group）にします。GPU が NVIDIA であることを狙った設定として実装されていますが、コード上のコンパイル条件は `STRATA_USE_HIP` が未定義であることです（後述）。

## 値と判定

`src/program/generate.cpp` で `std::getenv()` の結果を読み、値の先頭文字だけで判定します。文字列の数値変換や全体比較はしません。

| 環境変数の状態 | `nv_serial_faster` |
|---|---:|
| 未設定 | true |
| 空文字 | true（先頭は終端文字 `\0` であり `'0'` ではない） |
| 先頭文字が `0` | false（例: `0`, `0abc`） |
| それ以外 | true（例: `1`, `false`, `abc`, 空白で始まる文字列） |

`'0'` 以外の先頭文字はすべて同じ扱いです。大文字小文字、後続文字、数値としての妥当性は検査しません。未設定時は有効扱いなので、この既定を無効にするには `STRATA_BATCH_GROUPS_NV_SERIAL=0` のように先頭文字を `0` にします。

## 有効になる条件

この値が true でも、次の条件がすべて揃った場合に限り、自動グループ数を 1 にします。

- `--batch-groups` がコマンドラインで指定されていない。
- `--batch` が 2 slot 以上で、layer split がある。
- 自動計算したグループ数が 1 より大きい（slot 数を分割できる stage 数がある）。
- `later_stages == 1`、すなわち CUDA stage が2つ。
- `--batch-mtp` が有効でない。
- `--adapt-async 1` が指定されていない。
- `src/program/generate.cpp` が `STRATA_USE_HIP` 未定義でコンパイルされている。

明示した `--batch-groups 1` はその値のままです。明示した `--batch-groups auto` または数値指定もこの変数による既定変更の対象外です。`--batch-mtp` と `STRATA_BATCH_MTP_SERIAL` の組み合わせが先に判定され、`--adapt-async 1` は後に判定されます。これらが serial group を要求するときは、その理由で 1 group になります。条件を満たさない場合、通常の `auto` が選ぶ pipeline グループ数を使います。

コードの guard は `#if !defined(STRATA_USE_HIP)` であり、`STRATA_HIP_GFX906` を明示的に除外していません。その互換ビルドで当該ファイルがこの guard の条件でコンパイルされる場合も読み取り対象になります。したがって「NVIDIA だけ」というコメント上の説明より、実際の適用境界はこの macro と上記の実行条件で判断できます。

## 実行時の詳細

環境変数は `batch_groups_for()` が入力を組み立てるたびに読みます。結果は `resolve()` に渡され、未指定の既定 auto のときに限り、通常なら複数 group となる結果を `TwoCardsSerialFaster` として 1 group に上書きします。初期 batch slot 数の解決時と、VRAM に収まった slot 数への調整後に再解決されます。static cache はなく、サーバーの各リクエストで読み直すのではなく、generate 実行の batch 設定時に評価されます。

この既定変更が適用されると stderr に次の形式の案内が出ます（`G` は通常の auto が選んだ group 数）。

```text
strata generate: --batch-groups auto: 1 group of N slots - serial windows (measured faster than pipelined groups on two NVIDIA cards; STRATA_BATCH_GROUPS_NV_SERIAL=0 keeps the pipeline); --batch-groups G asks for the pipelined groups
```

`STRATA_BATCH_GROUPS_NV_SERIAL=0` なら、この案内の理由による 1 group 化は行われず、自動 pipeline が選ばれます。ただし他の理由（batch MTP、adapt async など）が serial group を要求する場合は別です。

## 根拠

- 変数の読み取りと HIP compile guard: `src/program/generate.cpp:5235-5248`。
- `--batch-groups` の CLI 指定状態と `auto` / 数値の解析: `src/program/generate.cpp:2595-2600`。
- 通常の auto group 数、環境値による 1 group 化、理由の優先順位: `include/strata/program/batch_groups.hpp:41-67`。
- 適用時の stderr 案内と再解決箇所: `src/program/generate.cpp:5313-5329,5378-5387`。
- group 数が複数の場合の pipeline 経路: `src/program/generate.cpp:11584-11612`。
- `docs/BATCHING.md:92` と `docs/release-notes-0.2.1.md:43` はこの既定動作を説明し、2x RTX A4000 での測定値を記載しています。これらの値は当該資料の条件で報告されたもので、別の機材・モデルでの性能を示すものではありません。
