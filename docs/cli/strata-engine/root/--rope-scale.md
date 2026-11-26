# `--rope-scale`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（推論エンジンの root） |
| オプション | `--rope-scale F` |
| 別名 | なし |
| 値 | `double` に変換される拡張係数。有限値で `0`（未指定扱い）または `1` 以上 |

## 役割

RoPE のコンテキスト拡張係数を指定します。これ単独では方式を選びません。実際に拡張を有効にするには、モデルの RoPE metadata で `linear` / `yarn` が選ばれているか、別途 `--rope-scaling linear` または `--rope-scaling yarn` を指定します。係数はモデルの `rope.scaling.factor` より優先されます。

## 使い方

```sh
# 例: YaRN で係数 2 の設定を使って token 列を処理する
strata --pack MODEL.strata --tokens 1,2,3 --rope-scaling yarn --rope-scale 2
```

## 値と既定値

- parser は `--rope-scale` の次の引数を `std::atof` で読み取ります。値の省略は stderr に `--rope-scale needs a value` を出して終了コード 2 になります。重複指定を拒否する処理はなく、後に指定した値が前の値を置き換えます（`engine/src/program/generate.cpp:3842-3846, 3872-3875`）。
- 既定値は `0` で、これは明示的な係数ではなく「フラグなし」として扱われます。モデルに factor があればそれを使い、なければ係数 1（拡張なし）が初期値です（`engine/src/program/generate.cpp:791-795, 5641-5646, 5715-5716`）。
- `0` は未指定扱いです。有限な負数と `0 < F < 1` は拒否され、係数は `F >= 1` でなければなりません。NaN / 無限大も拒否されます。`atof` が数値として読めない文字列を `0` に変換した場合は未指定扱いになります（parser と finite/range 検査: `engine/src/program/generate.cpp:3872-3875, 5243-5254`）。
- 明示した `1` はモデルの factor を上書きする値です。拡張係数を 1 にしますが、RoPE type 自体を `none` にする指定ではありません。

## 実行時の動作

起動時、CLI 値とモデルの RoPE metadata を解決し、`F > 0` なら factor に採用します。`F == 0` の場合はモデル factor が 1 より大きければそれを採用し、それ以外は構造体の既定値 1 のままです。RoPE type は別途 `--rope-scaling` またはモデル metadata から決まり、未指定の `--rope-scale` はその type の選択に影響しません（`engine/src/program/generate.cpp:5701-5723`）。

解決した設定は process 全体に一度設定され、session 初期化より前に固定されます。RoPE table を作る経路では係数が cos/sin table の計算に反映され、analytic kernel 経路では同じ設定値が kernel 引数として渡されます。実行中に切り替える CLI 機能はありません。K cache が RoPE 適用後の値を保持するためです（`engine/include/strata/kernels/rope_scaling.hpp:25-35, 186-190`; `engine/src/program/generate.cpp:5641-5646, 5759, 7738-7740`）。

`--rope-scaling none` またはモデル上の type が `none` なら、この係数を含む scaling knobs は設定から除かれ、RoPE scaling は行われません。`F > 1` など scaling 値を指定していた場合は stderr に「no rope scaling is active ... have no effect」という note が出ます（`engine/src/program/generate.cpp:5727-5739`）。一方、type が `linear` / `yarn` でも `--max-context` が学習時 context 以下なら位置拡張の必要がない旨の note が出ますが、係数に応じた設定は全角度に適用されます（同 `:5760-5771`）。

## 適用条件と副作用

- 有効な type（`linear` / `yarn`）での係数は RoPE の角度・テーブルまたは analytic kernel に作用します。YaRN の場合は `--yarn-*`、角度縮小の明示値は `--rope-freq-scale` と組み合わさります。`--rope-freq-scale` が 0 のときは `1 / factor` が使われます（`engine/src/program/generate.cpp:5715-5726`; `engine/include/strata/kernels/rope_scaling.hpp:169-182`）。
- 設定は起動時のみです。server/request 単位の変更はなく、同一プロセス内の session/cache が異なる scaling を混在させない設計です（`engine/src/program/generate.cpp:788-792`; `engine/include/strata/kernels/rope_scaling.hpp:30-35`）。
- このオプション自体はファイルを書き換えず、係数はモデルファイルに保存されません。推論エンジンの起動時設定に限られます。

## 出力とエラー

- parser で値が欠けていれば stderr に `--rope-scale needs a value` を出し、終了コード 2 です（`engine/src/program/generate.cpp:3844-3846`）。
- 非有限値は stderr に `a rope scaling knob is not a finite number`、1 未満の非ゼロ値は `--rope-scale ... must be >= 1` を出して終了コード 2 です（同 `:5243-5254`）。
- モデル metadata と他の scaling knobs を合わせた最終設定も検証されます。不正な組み合わせは stderr に `invalid rope scaling configuration: ...` を出して終了コード 2 です（`engine/src/program/generate.cpp:5749-5757`; `engine/include/strata/kernels/rope_scaling.hpp:169-183`）。
- scaling が有効なら解決 type、factor、freq scale、base、mscale、最大 context と学習時 context を stderr に表示します（`engine/src/program/generate.cpp:5759-5778`）。session 初期化失敗は `session_init failed` を stderr に出して終了コード 1 ですが、特定の `--rope-scale` 値に結び付く失敗経路とはソース上で確認できません（同 `:7738-7740`）。

## 根拠

- `engine/src/program/generate.cpp:791-795, 1268-1276` — option の説明、既定値と help 表示。
- `engine/src/program/generate.cpp:3842-3846, 3872-3875` — root parser、値の変換、値省略時の失敗。
- `engine/src/program/generate.cpp:5227-5254` — 有限性と係数範囲の検証。
- `engine/src/program/generate.cpp:5641-5646, 5701-5759` — モデル metadata との優先順位、設定解決、`none` 時の無効化、最終検証と process 設定。
- `engine/include/strata/kernels/rope_scaling.hpp:25-35, 169-190` — table / analytic 経路、検証規則、起動時固定の契約。
- `engine/src/program/generate.cpp:7738-7740` — session 初期化呼び出しと失敗出力。
