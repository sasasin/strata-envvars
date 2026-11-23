# `--dump`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal`（Metal 版、オフライン実行） |
| オプション | `--dump` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

Metal 版のオフライン推論中に、各層の中間値や MoE router の結果を `.npy` ファイルとして出力します。最後の prefill chunk の logits も保存し、保存先は `--out` が指定するディレクトリです。GPU の処理を途中で同期してから値を保存する箇所があるため、通常の推論に追加の同期とファイル I/O が発生します（`engine/src/hy4flash/metal/hy4_metal_main.cpp:808-813,1105-1126,1159-1165,1802-1809`）。

## 使い方

```sh
# 既存かつ書き込み可能な出力ディレクトリを指定して中間値を保存する
strata-hy4-metal --model model.strata --engram engram.strata --tokens prompt.ids --dump --out /path/to/existing-dump-dir
```

`--dump` 自体は値を取りません。`--out` のディレクトリは事前に存在するものを指定してください。例の `model.strata`、`engram.strata`、`prompt.ids` は実際の入力ファイルに置き換えます。

## 値と既定値

`--dump` は presence flag です。指定時に真、未指定時は偽で、数値やパスなどの値は受け取りません。別名や値の validation はありません。パーサは引数を左から走査し、このフラグを見つけると `dump = true` にします。同じフラグを複数回指定しても同じ真値のままです（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1490,1504-1517`）。

## 実行時の動作

パーサが設定した値は、オフライン `Runner` に `r.dump` として渡され、保存先には `--out` の値が `r.dump_dir` として渡されます。`--out` を省略した場合の値は `.`（起動時の作業ディレクトリ）です（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1489-1490,1510,1715-1723`）。

`--dump` が有効なとき、各推論 chunk の layer loop では、Engram 適用後（該当する場合）、attention 後、MLP 後の `x` を `x_L<層番号>_engram.npy`、`x_L<層番号>_attn.npy`、`x_L<層番号>_mlp.npy` として保存します。テンソル形状は `[T, 4, D/4]` です。`maybe_dump()` は保存前に `run_all()` を呼び、GPU dispatch を実行・同期します（`engine/src/hy4flash/metal/hy4_metal_main.cpp:808-813,1318-1325`）。

さらに各層の MoE 部分では、router の expert index と weight、および `cur_f` を `L<層番号>_topk_idx.npy`、`L<層番号>_topk_w.npy`、`L<層番号>_cur_mlp.npy` に保存します。最初の attention 層では追加で `L0_cur_attn.npy`、`L0_qr.npy`、`L0_q.npy`、`L0_attn_gate.npy`、`L0_attn_gated.npy`、`L0_attn_oproj.npy`、`L0_kv_cmpr.npy`、`L0_k_pe.npy` を出力します。半精度 buffer から取り出す値は float32 に変換してから保存されます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1105-1126,1159-1165`）。

最後の prefill chunk の logits は `logits.npy` に保存されます。`--all-logits` も指定するとその chunk の全 token 行、指定しない場合は最後の token 行だけを保存します（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1802-1809`）。各 chunk の中間値ファイル名には chunk 番号が含まれず、同じ名前へ繰り返し保存されるため、複数 chunk の実行では後の chunk が前のファイルを置き換えます。

`--serve` 経路ではモデル読み込み後に `hy4_serve_main()` へ移り、オフライン用 `Runner` の `dump` 設定と保存処理へ進みません。そのため、parser は `--dump` を受理しますが、serve 経路でこのフラグによる dump 出力は確認できません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1635-1675,1715-1723`）。

## 適用条件と副作用

- 中間値の dump は Metal runner のオフライン推論経路に適用されます。runner の layer loop が実行されなければ中間値ファイルは作られません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1635-1675,1318-1325`）。
- 保存先は `--out` のディレクトリです。`save_npy_f32()` は `fopen(path, "wb")` を使うため、同名ファイルがあれば切り詰めて上書きします。保存先ディレクトリを作る処理はこの保存関数にはなく、開けない場合はそのファイルの保存を黙ってスキップします（`engine/src/hy4flash/metal/hy4_metal_main.cpp:41-60`）。
- `fwrite()` の戻り値も検査されず、書き込み失敗をこの関数がエラーとして報告する経路は確認できません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:49-60`）。
- `--dump` は `logits.npy` の保存条件にもなります。`--save-logits` 単独でも logits 保存は行われますが、中間値の dump は有効になりません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1492,1554,1808`）。
- vision encode 内に別の dump helper はありますが、オフライン main から vision context への dump 設定代入は確認できませんでした。そのため、このオプションで画像 encoder の中間値が出力されるとは判断できません（helper: `engine/src/hy4flash/metal/hy4_metal_vision.h:168-170,216,256`。main の dump 設定転送: `engine/src/hy4flash/metal/hy4_metal_main.cpp:1715-1723`）。

## 出力とエラー

dump ファイルは NumPy v1 形式の little-endian float32 配列です。ファイル名と shape はコード中で固定されています（`engine/src/hy4flash/metal/hy4_metal_main.cpp:41-60,808-813,1108-1126,1161-1165,1802-1809`）。保存専用の成功ログや失敗ログはなく、ファイルを開けない場合も推論全体を止めずに戻ります。ほかの推論エラーの終了条件はこのオプション固有ではありません。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1488-1517` — `--dump` の parser 登録、値を消費しない presence flag、初期値。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:808-813,1318-1325` — 中間 activation の保存、shape、保存前の dispatch 実行。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1105-1126,1159-1165` — attention / router の dump 対象と変換。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1635-1675,1715-1723` — serve 分岐とオフライン Runner への設定転送。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1802-1809` — `--all-logits` と `logits.npy` の相互作用。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:41-60` — NPY 出力形式、上書き、ファイル open / write error の扱い。
