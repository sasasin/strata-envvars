# `STRATA_PIPELINE_AUTO_MIN_STAGES`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

`--pipeline-windows` を指定しなかった場合に、自動でパイプラインを有効化するために必要な最小 stage 数を決めます。この変数自体は機能の ON/OFF を決めず、`split_devs.size() + 1` と比較する閾値を設定します。自動判定が通ると `o.pipeline_windows` は `2` になり、各 stage に偶数・奇数 window 用の verifier を用意して window 間を重ねます。`engine/src/program/generate.cpp:6560-6579,13263-13274`。

この読み取りは `engine/src/program/generate.cpp` の `generate` 起動経路にあります。`--pipeline-windows N` を明示した場合は自動判定に入らず、この変数は参照されません。`engine/src/program/generate.cpp:1145-1150,4119,6560-6563`。

## 値と判定

`pw_auto` のときだけ、ブロック内の `static const char* am` として `std::getenv` で読み取ります。未設定なら `am == nullptr` となり、下表の条件別既定値を使います。設定済みなら値を `std::atoi` に渡し、`std::max(2, ...)` で下限 2 にします。上限の clamp や parse エラー検査はありません。`engine/src/program/generate.cpp:6560-6566`。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `--pipeline-windows` 省略、HIP build、後述の自動有効条件を満たす場合 | draft layer を first stage に置く既定が使える場合は 2 stages、それ以外は 3 stages | `atoi` の結果が 2 以上ならその値が必要 stage 数。例: `2`、`3`、`4tail` | `0`、`1`、`-1`、空文字、数値で始まらない文字列は `atoi` 結果が 2 未満となり、必要 stage 数は 2 |
| `--pipeline-windows N` を指定 | この変数を読まない | 該当なし | 該当なし |

`atoi` は文字列全体の厳密な検証ではありません。先頭の空白と符号の後にある整数部分を変換し、後続文字は無視します（例: `4tail` は 4、`1.5` は 1）。空文字・数値部分のない文字列は 0 になり、結果は 2 に丸められます。大文字小文字は文字列比較に使われません。`atoi` が `int` で表せない値の扱いはこのコードで検査されていません。`engine/src/program/generate.cpp:6563-6566`。

未設定時に 2 stages を既定とする条件は、MTP が指定され `--spec >= 2` で、`STRATA_MTP_FULL_HEAD` が未設定または先頭文字が `'1'` でなく、draft vocabulary subset file が存在し、HIP gfx12 の既定が使えることです。それ以外の未設定時は 3 stages です。ここでファイル存在を調べるのは `--mtp-draft-vocab`、または `<--mtp>/draft_vocab.bin` です。`engine/src/program/generate.cpp:2849-2867,6540-6546`。

## 有効になる条件

閾値を満たしても、次の自動判定条件をすべて満たさなければ自動では有効になりません。失敗時は `o.pipeline_windows = 0` となります。`engine/src/program/generate.cpp:6567-6579`。

- `--serve` が指定されていること。layer split は `--serve` がなければ設定検証で拒否されます。`engine/src/program/generate.cpp:4069,4803-4805,4848-4853`。
- 複数 GPU の layer split で、同一 GPU だけの split ではないこと。stage 数は `split_devs.size() + 1` です。`engine/src/program/generate.cpp:4808-4809,4856,6567`。
- HIP build であり、現在の device の architecture が `gfx_arch_is_gfx12_wmma` を満たすこと。非 HIP build では `on = false` にされます。`engine/src/program/generate.cpp:2849-2857,6568-6571`。
- `--mtp` があり、`--spec >= 2` であること。`engine/src/program/generate.cpp:6577`。
- `--batch` を使う場合は `STRATA_PW_WITH_BATCH` が先頭文字 `'1'` で始まること。`--peer-device` がないこと。helper cache のいずれも指定されていないこと。`--adapt-async` が無効であること。`engine/src/program/generate.cpp:6555-6559,6573-6578`。
- `--draft dflash2` を明示し、`--draft-fallback mtp` 以外にしていないこと。該当する DFlash2 経路では自動 pipeline を無効にします。`engine/src/program/generate.cpp:6574-6578`。

加えて `STRATA_PIPELINE_AUTO` が設定されていて `std::atoi` の結果が 0 なら、自動有効化を止めます。空文字、数値部分のない値、`0` などもこの条件に該当します。`STRATA_PIPELINE_AUTO` の `atoi` 結果が非 0 ならこの veto はかかりません。`engine/src/program/generate.cpp:6562,6567`。

この環境変数が 2 stages を閾値として許しても、`STRATA_MTP_STAGE0=0` は別の後段判定で drafter を first stage に置かない指定として使われます。閾値計算にはこの指定を参照しません。`engine/src/program/generate.cpp:6564-6567,6732-6737`。

## 実行時の詳細

`--pipeline-windows` の既定値は `-1`（未指定）です。明示した場合は CLI parser が `atoi` の結果を `0..2` に clamp するため、たとえば `--pipeline-windows 0` は自動判定を無効化し、正の値は環境変数の閾値を使わず明示値として後段の条件検査へ進みます。`engine/src/program/generate.cpp:1145-1150,4119,6560-6563`。

自動判定内では `static` なポインターを初回到達時に一度だけ `getenv` し、そのポインターを後続の自動判定でも再利用します。環境値の数値変換自体は `min_st` の計算時に行われます。したがって、最初の自動判定後に環境を変更しても、このキャッシュされた読み取りを更新するコードはありません。明示 CLI を使った呼び出しはこの static 初期化を行いません。`engine/src/program/generate.cpp:6560-6566`。

自動判定が通ると、実行時の `pipe` 条件（複数 stage、同一 GPU split でないこと等）に `o.pipeline_windows > 0` が渡されます。pipeline は各 stage に二つの verifier を使い、一方の window の hand-off を待つ間に次の window を前段 stage で進めます。`engine/src/program/generate.cpp:13263-13274`。

自動判定で ON/OFF のどちらになったかに関する専用ログは、OFF 時には出ません。閾値を超えて自動 ON になったときは enable 行が出ますが、後段の verifier / hand-off 初期化が失敗すれば起動は終了コード 1 で戻ります。`engine/src/program/generate.cpp:6580-6582,13276-13283,13440-13465`。

## ログと測定値

自動で有効になったときの stderr の書式（`%zu` は stage 数）:

```text
strata generate: --pipeline-windows 2 is on by default for a layer split of %zu stages (--pipeline-windows 0 or STRATA_PIPELINE_AUTO=0 turns it off)
```

pipeline 初期化後の stderr 書式は `strata serve: --pipeline-windows %d: two verifiers per stage, %d stages overlap across windows%s\n` です。最後の `%s` は GDN snapshot の状態に応じた補足です。stream 作成失敗は `strata serve: --pipeline-windows: stream creation failed`、2 個目の hand-off 割り当て失敗は `strata serve: --pipeline-windows: the second hand-off allocation failed` と出て終了コード 1 です。2 個目の verifier 初期化失敗も原因文字列付きで出力されます。`engine/src/program/generate.cpp:13276-13283,13440-13465,13756-13760`。

この変数自体について、現行ソースから測定値は確認できません。ここでは速度や生成 token への効果を断定しません。

## 根拠

- `engine/src/program/generate.cpp:1145-1150,4119` — CLI 既定値と `--pipeline-windows` の parse。
- `engine/src/program/generate.cpp:2849-2867,6540-6546` — HIP gfx12 判定と未設定時の stage 閾値に使う MTP 条件。
- `engine/src/program/generate.cpp:6555-6582` — 対象変数の唯一の実読み取り、自動判定、関連条件とログ。
- `engine/src/program/generate.cpp:6732-6737,13263-13283,13440-13465,13756-13760` — drafter 配置、pipeline の実行条件、初期化失敗と実行時ログ。
