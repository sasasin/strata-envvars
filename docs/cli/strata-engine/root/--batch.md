# `--batch`（alias: `--slots`）

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（推論エンジン引数） |
| オプション | `--batch N` |
| 別名 | `--slots N` |
| 値 | 整数として `atoi` で読み込む。標準経路の既定値は `0`（無効）。Qwen3.6 経路では実セッション数が最大 8。 |

## 役割

`--serve` で受け付ける複数リクエストに、それぞれ独立した会話状態（session/KV）を割り当て、decode の batch window でまとめて処理するスロット数を指定します。モデル family が Qwen3.6 以外なら通常の `generate.cpp` 経路、Qwen3.6 ならモデルヘッダーを見て `qwen35` 経路に切り替わり、同じ引数の制限・失敗動作は異なります。

## 使い方

```sh
# 通常のモデル経路で、serve の同時リクエスト用スロットを指定
strata --native model.gguf --serve --batch 4

# --slots は --batch と同じ parser 値を設定する
strata --native model.gguf --serve --slots 4
```

## 値と既定値

- 通常経路では `--batch` と `--slots` の値を `std::atoi` で整数化し、後に指定した方が `o.batch` を上書きします。数値形式の厳密な検査や範囲検査は parser にありません。引数を省略すると `0` です。値自体を省略した場合は `--batch needs a value` 等を stderr に出し、終了コード 2 で終了します（`engine/src/program/generate.cpp:1021,3842-3846,4041-4043`）。
- Qwen3.6 経路も両表記を `atoi` で読むが、初期値は `0` です。`Engine::init` は実セッション数を `max(1, min(N, 8))` に制限します。したがって `N > 8` は 8 セッションに丸められ、0・負値は1セッションになります（`engine/src/qwen35/q36_engine.cu:1640,1962-1967,5345-5347,5382`）。
- `--batch` を繰り返した場合や `--slots` と併用した場合、通常経路は後の値が有効です。Qwen3.6 でもループ内で同じ `batch` 変数を更新するため後の値が有効です（`engine/src/program/generate.cpp:4041-4042`、`engine/src/qwen35/q36_engine.cu:5348-5383`）。

## 実行時の動作

### 通常モデル経路

`--batch` は `--serve` が必要で、2スロット以上でなければ有効になりません。`--serve` なし、または値が 2 未満なら警告を stderr に出して `o.batch=0` に戻し、通常の単一リクエスト経路を続けます。layer split の各 stage が別 GPU にない場合も同様に無効になります（`engine/src/program/generate.cpp:7954-7961`）。

有効時は各スロットにモデルの最大 context に対応する独立 session state を確保します。各 session の KV は GPU/host memory を消費し、CUDA では確保可能なスロット数が指定数より少ないと、確保に失敗した slot 以降を打ち切ります。2 slot を確保できなければ警告後に batch を無効化し、確保数が足りれば実際の batch 数を確保できた数に下げます。CUDA の VRAM 使用量を stderr に出し、session 分の VRAM は expert cache が使える領域から差し引かれます（`engine/src/program/generate.cpp:8000-8018,8065-8116`）。

batch window が扱える row 数を超える場合は、`--batch-mtp` の有無や layer split/group 構成に応じてスロット数を切り詰め、警告を出します（`engine/src/program/generate.cpp:7937-7952,7962-7968,8103-8110`）。リクエストは空き slot に割り当てられ、slot ごとに prompt と会話状態を保持しながら、batch window ごとに次の token をまとめて処理します（`engine/src/program/generate.cpp:16742-16749,19310-19330`）。

### Qwen3.6 family 経路

`--model` または `--native` の GGUF が Qwen3.6 family と判定されると、この経路へ振り分けられます（`engine/src/program/generate.cpp:3804-3818`）。`--batch` は serve の必須条件として検査されず、指定数を `Engine::init` に渡します。ただし内部上限は 8 session です（`engine/src/qwen35/q36_engine.cu:1962-1967,5522,5562`）。通常の用途は `--serve` で複数要求を処理することです。各 session は独立した recurrent state と KV cache を持ち、複数 slot の row を同じ decode window で実行します（`engine/src/qwen35/q36_engine.cu:1684-1686`）。

初期化時に session 数・context に応じた cache の概算 VRAM を stderr に出します。必要量に 1 GiB の余裕を加えた値が空き VRAM を超えると、不足メッセージを出して終了コード 1 で終了します（`engine/src/qwen35/q36_engine.cu:2142-2159`）。serve 開始時は `INFO batch_slots=N slot_cache=1` を stdout に出します（複数 session の場合、`engine/src/qwen35/q36_engine.cu:5281-5285`）。

## 相互作用と適用条件

- 通常経路では `--batch-groups` が layer split 上の slot pipeline を制御します。groups が 1 より大きい場合、layer split がない、または slot 数を割り切れない構成では警告して groups を 1 に戻します（`engine/src/program/generate.cpp:7994-7999`）。詳細は [`--batch-groups`](--batch-groups.md) を参照してください。
- `--batch-mtp` は batch slot ごとの MTP proposal 処理を追加する別オプションです。通常経路で適用される条件や無効化理由は `generate.cpp` 内の gate にあり、batch row の上限・処理形状にも影響します（`engine/src/program/generate.cpp:7791-7802,7842-7871,7928-7940`）。
- Qwen3.6 の `--batch-mtp` は batch が2以上で `--mtp N` の N が有効な場合にだけ有効です（`engine/src/qwen35/q36_engine.cu:5456,5556-5560`）。
- 通常経路では `--batch` を有効にしても、起動時の session 確保結果や window の row 上限によって要求数より実数が少なくなることがあります。Qwen3.6 経路では8を超える要求は最大8 session までです。

## 出力とエラー

- 通常経路の非対応条件・row 上限・memory 制約は主に stderr の `WARNING` または診断行で通知され、batch を縮小・無効化して処理を続けます（`engine/src/program/generate.cpp:7957-7968,8093-8116`）。
- Qwen3.6 経路で複数 session 分の VRAM が足りない場合は stderr に `not enough VRAM for ... slots` を出し、終了コード 1 になります（`engine/src/qwen35/q36_engine.cu:2155-2159`）。
- `atoi` による値の変換は両 parser に共通します。非数値入力や整数範囲外入力の厳密な扱いは parser 側で検証されていないため、移植可能な受理範囲としては確定できません。

## 根拠

- `engine/src/program/generate.cpp:1021-1027` — 通常経路の batch 既定値と関連設定。
- `engine/src/program/generate.cpp:1317-1323` — `--serve` 専用オプションとしての help 記載。
- `engine/src/program/generate.cpp:3804-3818` — Qwen3.6 family の parser/実行経路への切替。
- `engine/src/program/generate.cpp:4041-4043` — `--batch` と `--slots` の parser 登録。
- `engine/src/program/generate.cpp:7954-7968,8000-8116` — 適用条件、memory・window 制限、縮小と出力。
- `engine/src/program/generate.cpp:16742-16749,19310-19330` — 通常経路の slot 状態と request admission。
- `engine/src/qwen35/q36_engine.cu:1640,1684-1686,1962-1967` — Qwen3.6 の上限と各 session の役割。
- `engine/src/qwen35/q36_engine.cu:2142-2159,5281-5285,5345-5383,5522,5556-5562` — Qwen3.6 の memory 判定、出力、parser、serve 開始。
