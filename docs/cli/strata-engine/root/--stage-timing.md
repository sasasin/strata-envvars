# `--stage-timing`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査開始時の作業ツリーは `## main...origin/main` で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジン。診断メッセージ上の処理名は `strata generate`） |
| オプション | `--stage-timing` |
| 別名 | なし |
| 値 | なし。フラグを指定すると有効 |

## 役割

推論中にレイヤー内の区間へ CUDA event を記録し、実行終了時に区間ごとの GPU 上の経過時間を stderr に表示します。これはカーネル数の比率ではありません。計測区間にはホストが次の仕事を投入するまで GPU が待つ時間も含まれ得るため、純粋な GPU 処理時間の比較としては読めません（`src/core/layer.cpp:1039-1044,1087-1105`）。

## 使い方

```sh
strata --pack /path/to/model.pack --tokens 1,2,3 --stage-timing --no-capture
```

このエンジンは tokenizer を持たず、通常の生成では `--tokens` または `--tokens-file` が必要です。上の pack パスと token ID は利用環境に合わせてください（`src/program/generate.cpp:2425-2440,3174-3178`）。

## 値と既定値

- 値を取らない真偽値フラグです。`Options::stage_timing` の初期値は `false` で、parser が `--stage-timing` を読むと `true` にします（`src/program/generate.cpp:510-512,2504-2509`）。
- 重複指定しても同じ真偽値を再度 `true` にするだけです。値の範囲検証はありません。値を続けて書くと、その文字列は別引数として解析され、未知引数なら usage を表示して終了コード 2 になります（`src/program/generate.cpp:2416-2423,2507,2787-2792`）。
- 未指定時はイベント計測・集計を行いません。

## 実行時の動作

- `--no-capture` との併用が必須です。指定がなければ、stream capture 中の event record は無視されて誤解を招く値になるとして stderr に理由と併用方法を表示し、終了コード 2 で終了します（`src/program/generate.cpp:6881-6889`）。
- 有効時は最大64レイヤー、20区間分の開始・終了 CUDA event を作成します。作成に失敗した場合は `stage_timing_enable failed` を stderr に出し、終了コード 1 になります（`src/core/layer.cpp:1045-1067`; 呼び出し元 `src/program/generate.cpp:6891-6894`）。
- 主な区間は attention 側の hyper-connection read、attention block、write、FFN 側の read、MoE route/finish/write です。GDN 内部については活性値量子化、QKV GEMV、conv+SiLU、norm、gate、GDN step、出力 norm、出力 GEMV も記録します（`src/program/generate.cpp:6895-6912`; 記録箇所 `src/core/layer.cpp:1534-1572,1611-1632,261-276,298-383`）。
- `--stage-timing` は fused hyper-connection 経路の選択条件から除外されるため、その経路を使う設定でも fused GR を無効にし、read/write を分けた計測可能な形にします（`src/program/generate.cpp:3927-3932`）。
- 推論終了時に `stage_timing_report` が CUDA device を同期し、記録済み event の経過時間をレイヤーごとに加算します。stderr には区間別の合計 ms/token、ms/layer、割合、区間合計、および attention block のレイヤー別時間と GDN/QSA 別集計を出します（`src/core/layer.cpp:1087-1123`; 呼び出し元 `src/program/generate.cpp:16865`）。各レイヤー・区間の event は同じハンドルを再利用する実装です（`src/core/layer.cpp:1047-1052,1079-1085`）。

## 適用条件と副作用

- `--no-capture` の通常 launch 経路でのみ使用できます。capture を使う通常経路では拒否されます（`src/program/generate.cpp:6881-6889`）。
- CUDA event を多数作成して保持し、終了時に device 全体を同期します。計測自体は GPU の実行中には同期しない設計ですが、イベント記録と最後の同期は実行時の追加処理です（`src/core/layer.cpp:1045-1067,1079-1089`）。
- event 間の時間は GPU 上の区間時間として表示されますが、非 capture 経路ではホスト側の投入待ちも区間に含み得ます。したがってカーネル単体の実行時間や純粋な GPU 下限を示すものではありません（`src/core/layer.cpp:1039-1044`; parser 用 usage もこの注意を記載: `src/program/generate.cpp:972-973`）。
- stage timing 専用のファイル出力はありません。レポートは stderr、生成トークン等の通常出力は stdout です（`src/core/layer.cpp:1099-1122`; `src/program/generate.cpp:16865-16872`）。

## 出力とエラー

- `--no-capture` がない場合: stderr に `Pass --no-capture as well.` を含むエラーを出し、終了コード 2（`src/program/generate.cpp:6884-6889`）。
- CUDA event の初期化に失敗した場合: stderr に `stage_timing_enable failed` を出し、終了コード 1（`src/program/generate.cpp:6891-6894`）。
- 正常時: 実行末尾で stderr に per-stage と per-layer の集計を表示し、その後通常の生成結果を stdout に出します（`src/core/layer.cpp:1099-1122`; `src/program/generate.cpp:16865-16872`）。
- ソース内の usage 文は「per-stage KERNEL-COUNT shares」と説明していますが、実装が出力するのは event の経過時間と時間比率です。ここでは実装を説明の根拠とし、usage 文との不一致を記録します（`src/program/generate.cpp:972-973`; `src/core/layer.cpp:1091-1105`）。

## 根拠と調査範囲

- parser と既定値: `src/program/generate.cpp:510-512,2416-2423,2504-2509`
- capture 条件、失敗経路、区間名: `src/program/generate.cpp:6881-6912`
- 計測対象の記録箇所と event 集計: `src/core/layer.cpp:261-276,1045-1123,1534-1572,1611-1632`
- 実行経路での fused GR 条件、レポート呼び出し: `src/program/generate.cpp:3927-3932,16865-16872`

同一 revision の実行バイナリは使わず、CLI `--help` も実行していません。usage の記載はソース中の parser 実装と照合しました。GPU/各 backend で実測した値や event 作成失敗時のデバイス固有挙動は調査していません。
